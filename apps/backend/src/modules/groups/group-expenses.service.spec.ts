import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
} from '@nestjs/common';
import { SplitType } from '@prisma/client';
import { InMemoryPrismaService } from '../../../test/e2e-harness/in-memory-prisma.service';
import { PrismaService } from '../../prisma/prisma.service';
import {
  computeDeterministicEqualSplits,
  computeGreedySettlementSuggestions,
  GroupExpensesService,
} from './group-expenses.service';

describe('GroupExpensesService Math & Invariants (W10 WP-EXP-01 & WP-EXP-02)', () => {
  it('distributes 100.000 VND / 3 deterministically as 33.334 + 33.333 + 33.333 regardless of input order/case', () => {
    const u1 = '11111111-1111-4111-8111-111111111111';
    const u2 = '22222222-2222-4222-8222-222222222222';
    const u3 = '33333333-3333-4333-8333-333333333333';

    const permutations = [
      [u1, u2, u3],
      [u3.toUpperCase(), u2, u1.toUpperCase()],
      [u2.toUpperCase(), u3, u1],
    ];
    for (const perm of permutations) {
      const r = computeDeterministicEqualSplits(100000, perm);
      expect(r).toEqual([
        { userId: u1, shareAmount: 33334 },
        { userId: u2, shareAmount: 33333 },
        { userId: u3, shareAmount: 33333 },
      ]);
      expect(r.reduce((acc, s) => acc + s.shareAmount, 0)).toBe(100000);
    }

    expect(() =>
      computeDeterministicEqualSplits(2, [u1, u2, u3]),
    ).toThrow(BadRequestException);
  });

  it('produces 3 deterministic greedy transfer suggestions for the 4-member benchmark (7 bill obligations -> 3 transfers)', () => {
    const an = '00000000-0000-4000-8000-000000000001';
    const binh = '00000000-0000-4000-8000-000000000002';
    const chi = '00000000-0000-4000-8000-000000000003';
    const dung = '00000000-0000-4000-8000-000000000004';

    const suggestions = computeGreedySettlementSuggestions([
      { userId: an, netBalance: 166666n },
      { userId: binh, netBalance: 100000n },
      { userId: chi, netBalance: -133333n },
      { userId: dung, netBalance: -133333n },
    ]);

    expect(suggestions).toEqual([
      { fromUserId: chi, toUserId: an, amount: 133333 },
      { fromUserId: dung, toUserId: binh, amount: 100000 },
      { fromUserId: dung, toUserId: an, amount: 33333 },
    ]);
  });

  it('forbids debtor from self-confirming settlement EVEN WHEN debtor is Group admin, enforces idempotency, and locks expense deletion after settlement', async () => {
    const mem = new InMemoryPrismaService();
    mem.seed();
    const prisma = mem as unknown as PrismaService;
    const service = new GroupExpensesService(prisma);

    const adminUser = await mem.user.create({
      data: {
        email: 'admin@gomate.vn',
        passwordHash: 'h',
        profile: { create: { displayName: 'Admin Đang Nợ' } },
      },
    });
    const memberCreditor = await mem.user.create({
      data: {
        email: 'creditor@gomate.vn',
        passwordHash: 'h',
        profile: { create: { displayName: 'Chủ Nợ Member' } },
      },
    });
    const adminId = String(adminUser.id);
    const creditorId = String(memberCreditor.id);

    const group = await mem.group.create({
      data: {
        name: 'Nhóm Chia Chi Phí',
        members: { create: { userId: adminId, role: 'admin' } },
      },
    });
    await mem.groupMember.create({
      data: { groupId: group.id, userId: creditorId, role: 'member' },
    });

    // Member pays 100.000 VND split 60k (admin) / 40k (creditor) -> admin owes creditor 60.000 VND!
    const exp = await service.createExpense(group.id, creditorId, {
      title: 'Vé tàu tham quan vịnh',
      amount: 100000,
      paidByUserId: creditorId,
      splitType: SplitType.CUSTOM,
      customSplits: [
        { userId: adminId, shareAmount: 60000 },
        { userId: creditorId, shareAmount: 40000 },
      ],
    });
    expect(exp.amount).toBe(100000);

    // Admin tries to self-confirm their OWN 60.000 VND debt -> MUST BE REJECTED 403!
    await expect(
      service.createSettlement(group.id, adminId, {
        debtorId: adminId,
        creditorId,
        amount: 60000,
      }),
    ).rejects.toThrow(ForbiddenException);

    // Creditor confirms receipt twice with same clientRequestId -> recorded ONLY ONCE
    const s1 = await service.createSettlement(group.id, creditorId, {
      debtorId: adminId,
      creditorId,
      amount: 60000,
      clientRequestId: 'settle-once-1',
    });
    const s2 = await service.createSettlement(group.id, creditorId, {
      debtorId: adminId,
      creditorId,
      amount: 60000,
      clientRequestId: 'settle-once-1',
    });
    expect(s1.settlement.id).toBe(s2.settlement.id);
    expect(s2.updatedBalances.every((b) => b.netBalance === 0)).toBe(true);

    // RBAC checked BEFORE idempotency: Admin debtor retrying existing clientRequestId MUST STILL BE 403!
    await expect(
      service.createSettlement(group.id, adminId, {
        debtorId: adminId,
        creditorId,
        amount: 60000,
        clientRequestId: 'settle-once-1',
      }),
    ).rejects.toThrow(ForbiddenException);

    // Same clientRequestId with DIFFERENT payload -> 409 ConflictException!
    await expect(
      service.createSettlement(group.id, creditorId, {
        debtorId: adminId,
        creditorId,
        amount: 50000,
        clientRequestId: 'settle-once-1',
      }),
    ).rejects.toThrow(ConflictException);

    // Overpayment by 1 VND rejected
    await expect(
      service.createSettlement(group.id, creditorId, {
        debtorId: adminId,
        creditorId,
        amount: 1,
        clientRequestId: 'settle-over',
      }),
    ).rejects.toThrow(BadRequestException);

    // Expense deletion locked (409) across the ENTIRE group once group has settlement
    const exp2 = await service.createExpense(group.id, adminId, {
      title: 'Cà phê sau đối soát',
      amount: 30000,
      paidByUserId: adminId,
      splitType: SplitType.EQUAL,
      participantIds: [adminId, creditorId],
    });
    expect(exp2.canDelete).toBe(false);
    await expect(
      service.deleteExpense(group.id, exp.id, adminId),
    ).rejects.toThrow(ConflictException);
    await expect(
      service.deleteExpense(group.id, exp2.id, adminId),
    ).rejects.toThrow(ConflictException);
  });
});
