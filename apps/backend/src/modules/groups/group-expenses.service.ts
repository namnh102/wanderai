import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import {
  ExpenseCategory,
  Prisma,
  SplitType,
  TravelStyle,
} from '@prisma/client';
import { PrismaService } from '../../prisma/prisma.service';
import {
  SAFE_BUDDY_USER_SELECT,
  SafeBuddyPeerView,
  toSafeBuddyPeerView,
} from '../matches/matches.service';
import { CreateExpenseDto, CreateSettlementDto } from './dto/group-expenses.dto';
import {
  GROUP_ERROR_CODES,
  GROUP_ROLES,
  GroupRole,
  normalizeUuid,
} from './groups.constants';

type DbClient = PrismaService | Prisma.TransactionClient;

const MAX_INT32_BIGINT = 2147483647n;
const DELETED_ACCOUNT_LABEL = 'Tài khoản đã xóa';

interface SelectedSafeUser {
  id: string;
  deletedAt: Date | null;
  profile: {
    displayName: string | null;
    avatar: string | null;
    bio: string | null;
    nationality: string | null;
    languages: string[];
  } | null;
  preferences: {
    travelStyle: TravelStyle | null;
    interests: string[];
  } | null;
}

export interface ExpenseSplitView {
  id: string;
  userId: string;
  shareAmount: number;
  user: SafeBuddyPeerView;
}

export interface ExpenseView {
  id: string;
  groupId: string;
  tripId: string | null;
  title: string;
  amount: number;
  currency: string;
  category: ExpenseCategory;
  splitType: SplitType;
  expenseDate: Date;
  notes: string | null;
  paidByUserId: string;
  paidBy: SafeBuddyPeerView;
  createdByUserId: string;
  createdBy: SafeBuddyPeerView;
  createdAt: Date;
  canDelete: boolean;
  splits: ExpenseSplitView[];
}

export interface ExpenseListView {
  groupId: string;
  currency: string;
  hasSettlements: boolean;
  totalSpent: number;
  expenseCount: number;
  expenses: ExpenseView[];
}

export interface MemberBalanceView {
  userId: string;
  user: SafeBuddyPeerView;
  isActiveMember: boolean;
  paidAmount: number;
  owedAmount: number;
  outgoingSettlement: number;
  incomingSettlement: number;
  netBalance: number;
}

export interface SuggestedSettlementView {
  fromUserId: string;
  fromUser: SafeBuddyPeerView;
  toUserId: string;
  toUser: SafeBuddyPeerView;
  amount: number;
}

export interface SettlementView {
  id: string;
  groupId: string;
  tripId: string | null;
  debtorId: string;
  debtor: SafeBuddyPeerView;
  creditorId: string;
  creditor: SafeBuddyPeerView;
  createdByUserId: string;
  amount: number;
  currency: string;
  notes: string | null;
  settledAt: Date;
}

export interface SettlementPlanView {
  groupId: string;
  currency: string;
  totalSpent: number;
  totalOutstandingDebt: number;
  zeroSumVerified: boolean;
  balances: MemberBalanceView[];
  suggestedTransactions: SuggestedSettlementView[];
  settlements: SettlementView[];
}

function toSafeNumber(val: bigint): number {
  const num = Number(val);
  if (!Number.isSafeInteger(num)) {
    throw new BadRequestException({
      errorCode: 'VALIDATION_ERROR',
      message: 'Tổng giá trị vượt giới hạn số nguyên an toàn',
    });
  }
  return num;
}

function formatPossiblyDeletedUser(
  userId: string,
  user: SelectedSafeUser | null | undefined,
): SafeBuddyPeerView {
  if (!user || user.deletedAt !== null) {
    return {
      id: userId,
      displayName: DELETED_ACCOUNT_LABEL,
      avatar: null,
      bio: null,
      nationality: null,
      languages: [],
      travelStyle: null,
      interests: [],
    };
  }
  return toSafeBuddyPeerView(user);
}

/**
 * Pure deterministic VND integer equal split helper:
 * Sorts unique lowercase UUIDs ascending (`userId ASC`), distributes `remainder` (+1 VND)
 * to the first `remainder` entries. Example: 100_000 / 3 => [33_334, 33_333, 33_333].
 */
export function computeDeterministicEqualSplits(
  amount: number,
  rawParticipantIds: string[],
): Array<{ userId: string; shareAmount: number }> {
  const uniqueSorted = Array.from(
    new Set(rawParticipantIds.map((id) => normalizeUuid(id))),
  ).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

  const n = uniqueSorted.length;
  if (n === 0) {
    throw new BadRequestException({
      errorCode: GROUP_ERROR_CODES.EXPENSE_INVALID_PARTICIPANT,
      message: 'Cần ít nhất 1 thành viên tham gia chia chi phí',
    });
  }
  if (amount < n) {
    throw new BadRequestException({
      errorCode: GROUP_ERROR_CODES.EXPENSE_AMOUNT_TOO_SMALL_FOR_SPLIT,
      message:
        'Số tiền phải lớn hơn hoặc bằng số người tham gia chia đều để mỗi người nhận tối thiểu 1 VND',
    });
  }

  const baseShare = Math.floor(amount / n);
  const remainder = amount % n;

  return uniqueSorted.map((userId, index) => ({
    userId,
    shareAmount: index < remainder ? baseShare + 1 : baseShare,
  }));
}

/**
 * Pure deterministic greedy debt simplification suggestion generator:
 * Suggests how to reduce the number of transfer transactions (`<= M - 1` at normal scale),
 * re-sorting creditors and debtors by `(remaining DESC, userId ASC)` after every transfer.
 */
export function computeGreedySettlementSuggestions(
  balanceEntries: ReadonlyArray<{ userId: string; netBalance: bigint }>,
): Array<{ fromUserId: string; toUserId: string; amount: number }> {
  const creditors = balanceEntries
    .filter((b) => b.netBalance > 0n)
    .map((b) => ({ userId: normalizeUuid(b.userId), remaining: b.netBalance }));
  const debtors = balanceEntries
    .filter((b) => b.netBalance < 0n)
    .map((b) => ({
      userId: normalizeUuid(b.userId),
      remaining: -b.netBalance,
    }));

  const sortBucket = (
    list: Array<{ userId: string; remaining: bigint }>,
  ): void => {
    list.sort((a, b) => {
      if (b.remaining > a.remaining) return 1;
      if (b.remaining < a.remaining) return -1;
      return a.userId < b.userId ? -1 : a.userId > b.userId ? 1 : 0;
    });
  };

  const suggestions: Array<{
    fromUserId: string;
    toUserId: string;
    amount: number;
  }> = [];

  while (creditors.length > 0 && debtors.length > 0) {
    sortBucket(creditors);
    sortBucket(debtors);

    const creditor = creditors[0];
    const debtor = debtors[0];
    const transfer =
      creditor.remaining < debtor.remaining
        ? creditor.remaining
        : debtor.remaining;

    let remChunk = transfer;
    while (remChunk > 0n) {
      const chunk =
        remChunk > MAX_INT32_BIGINT ? MAX_INT32_BIGINT : remChunk;
      suggestions.push({
        fromUserId: debtor.userId,
        toUserId: creditor.userId,
        amount: Number(chunk),
      });
      remChunk -= chunk;
    }

    creditor.remaining -= transfer;
    debtor.remaining -= transfer;

    if (creditor.remaining === 0n) {
      creditors.shift();
    }
    if (debtor.remaining === 0n) {
      debtors.shift();
    }
  }

  return suggestions;
}

@Injectable()
export class GroupExpensesService {
  constructor(private readonly prisma: PrismaService) {}

  private async _lockGroup(
    tx: Prisma.TransactionClient,
    groupId: string,
  ): Promise<void> {
    if (typeof (tx as { $queryRaw?: unknown }).$queryRaw !== 'function') {
      return;
    }
    await tx.$queryRaw`SELECT id FROM "groups" WHERE id = ${groupId}::uuid FOR UPDATE`;
  }

  private async _resolveGroupContext(
    db: DbClient,
    rawGroupId: string,
    rawActorId: string,
  ): Promise<{
    groupId: string;
    actorId: string;
    linkedTripId: string | null;
    isTripOwner: boolean;
    myGroupRole: GroupRole;
    activeMemberIds: Set<string>;
    allMemberMap: Map<string, { userId: string; isActive: boolean; user: SelectedSafeUser | null }>;
  }> {
    const groupId = normalizeUuid(rawGroupId);
    const actorId = normalizeUuid(rawActorId);

    const group = await db.group.findUnique({
      where: { id: groupId },
    });
    if (!group) {
      throw new NotFoundException({
        errorCode: GROUP_ERROR_CODES.GROUP_NOT_FOUND,
        message: 'Nhóm đồng hành không tồn tại',
      });
    }

    const memberRows = await db.groupMember.findMany({
      where: { groupId: group.id },
      include: { user: { select: SAFE_BUDDY_USER_SELECT } },
    });

    const activeMemberIds = new Set<string>();
    const allMemberMap = new Map<
      string,
      { userId: string; isActive: boolean; user: SelectedSafeUser | null }
    >();

    let actorRoleRaw: string | null = null;
    for (const m of memberRows) {
      const uid = normalizeUuid(m.userId);
      const userObj = (m.user as SelectedSafeUser | null) ?? null;
      const isActive = userObj !== null && userObj.deletedAt === null;
      allMemberMap.set(uid, { userId: m.userId, isActive, user: userObj });
      if (isActive) {
        activeMemberIds.add(uid);
        if (uid === actorId) {
          actorRoleRaw = m.role;
        }
      }
    }

    if (!activeMemberIds.has(actorId)) {
      throw new ForbiddenException({
        errorCode: GROUP_ERROR_CODES.GROUP_FORBIDDEN,
        message: 'Bạn không phải thành viên hợp lệ của nhóm này',
      });
    }

    let linkedTripId: string | null = null;
    let isTripOwner = false;
    if (group.tripId) {
      const trip = await db.trip.findFirst({
        where: { id: group.tripId, deletedAt: null },
        select: { id: true, userId: true },
      });
      if (trip) {
        linkedTripId = trip.id;
        isTripOwner = normalizeUuid(trip.userId) === actorId;
      }
    }

    const myGroupRole: GroupRole =
      actorRoleRaw === GROUP_ROLES.ADMIN || isTripOwner
        ? GROUP_ROLES.ADMIN
        : GROUP_ROLES.MEMBER;

    return {
      groupId: group.id,
      actorId,
      linkedTripId,
      isTripOwner,
      myGroupRole,
      activeMemberIds,
      allMemberMap,
    };
  }

  private async _hydrateUserMap(
    db: DbClient,
    userIds: Iterable<string>,
    knownMap: Map<
      string,
      { userId: string; isActive: boolean; user: SelectedSafeUser | null }
    >,
  ): Promise<Map<string, SafeBuddyPeerView>> {
    const out = new Map<string, SafeBuddyPeerView>();
    const missingIds: string[] = [];

    for (const rawId of userIds) {
      const uid = normalizeUuid(rawId);
      if (out.has(uid)) continue;
      const known = knownMap.get(uid);
      if (known) {
        out.set(uid, formatPossiblyDeletedUser(known.userId, known.user));
      } else {
        missingIds.push(uid);
      }
    }

    for (const uid of missingIds) {
      const user = (await db.user.findUnique({
        where: { id: uid },
        select: SAFE_BUDDY_USER_SELECT,
      })) as SelectedSafeUser | null;
      out.set(uid, formatPossiblyDeletedUser(uid, user));
    }

    return out;
  }

  private async _computeLedger(
    db: DbClient,
    groupId: string,
    activeMemberIds: Set<string>,
    allMemberMap: Map<
      string,
      { userId: string; isActive: boolean; user: SelectedSafeUser | null }
    >,
  ): Promise<{
    totalSpent: bigint;
    totalOutstandingDebt: bigint;
    zeroSumVerified: boolean;
    balanceByUser: Map<string, bigint>;
    balances: MemberBalanceView[];
    suggestedTransactions: SuggestedSettlementView[];
    settlements: SettlementView[];
  }> {
    const expenses = await db.expense.findMany({
      where: { groupId, deletedAt: null },
      include: { splits: true },
    });
    const settlements = await db.settlement.findMany({
      where: { groupId },
      orderBy: [{ settledAt: 'desc' }, { createdAt: 'desc' }],
    });

    const allUserIds = new Set<string>();
    for (const uid of allMemberMap.keys()) {
      allUserIds.add(uid);
    }
    for (const exp of expenses) {
      allUserIds.add(normalizeUuid(exp.paidByUserId));
      for (const sp of exp.splits) {
        allUserIds.add(normalizeUuid(sp.userId));
      }
    }
    for (const st of settlements) {
      allUserIds.add(normalizeUuid(st.debtorId));
      allUserIds.add(normalizeUuid(st.creditorId));
      allUserIds.add(normalizeUuid(st.createdByUserId));
    }

    const userViewMap = await this._hydrateUserMap(db, allUserIds, allMemberMap);

    const paidMap = new Map<string, bigint>();
    const owedMap = new Map<string, bigint>();
    const outSettleMap = new Map<string, bigint>();
    const inSettleMap = new Map<string, bigint>();

    const ledgerUsers = new Set<string>(allMemberMap.keys());

    let totalSpent = 0n;
    for (const exp of expenses) {
      const amt = BigInt(exp.amount);
      totalSpent += amt;
      const payerUid = normalizeUuid(exp.paidByUserId);
      ledgerUsers.add(payerUid);
      paidMap.set(payerUid, (paidMap.get(payerUid) ?? 0n) + amt);
      for (const sp of exp.splits) {
        const sUid = normalizeUuid(sp.userId);
        ledgerUsers.add(sUid);
        owedMap.set(sUid, (owedMap.get(sUid) ?? 0n) + BigInt(sp.shareAmount));
      }
    }

    for (const st of settlements) {
      const amt = BigInt(st.amount);
      const dUid = normalizeUuid(st.debtorId);
      const cUid = normalizeUuid(st.creditorId);
      ledgerUsers.add(dUid);
      ledgerUsers.add(cUid);
      outSettleMap.set(dUid, (outSettleMap.get(dUid) ?? 0n) + amt);
      inSettleMap.set(cUid, (inSettleMap.get(cUid) ?? 0n) + amt);
    }

    const sortedLedgerUsers = Array.from(ledgerUsers).sort((a, b) =>
      a < b ? -1 : a > b ? 1 : 0,
    );

    const balanceByUser = new Map<string, bigint>();
    let netSum = 0n;
    let totalOutstandingDebt = 0n;

    const balances: MemberBalanceView[] = [];
    for (const uid of sortedLedgerUsers) {
      const paid = paidMap.get(uid) ?? 0n;
      const owed = owedMap.get(uid) ?? 0n;
      const outSt = outSettleMap.get(uid) ?? 0n;
      const inSt = inSettleMap.get(uid) ?? 0n;
      const net = paid - owed + outSt - inSt;

      // Hide former members who have 0 activity or have already settled to 0 and left the group
      if (!allMemberMap.has(uid) && net === 0n) {
        balanceByUser.set(uid, 0n);
        continue;
      }

      balanceByUser.set(uid, net);
      netSum += net;
      if (net > 0n) {
        totalOutstandingDebt += net;
      }

      balances.push({
        userId: uid,
        user:
          userViewMap.get(uid) ?? formatPossiblyDeletedUser(uid, undefined),
        isActiveMember: activeMemberIds.has(uid),
        paidAmount: toSafeNumber(paid),
        owedAmount: toSafeNumber(owed),
        outgoingSettlement: toSafeNumber(outSt),
        incomingSettlement: toSafeNumber(inSt),
        netBalance: toSafeNumber(net),
      });
    }

    const rawSuggestions = computeGreedySettlementSuggestions(
      Array.from(balanceByUser.entries()).map(([userId, netBalance]) => ({
        userId,
        netBalance,
      })),
    );

    const suggestedTransactions: SuggestedSettlementView[] = rawSuggestions.map(
      (s) => ({
        fromUserId: s.fromUserId,
        fromUser:
          userViewMap.get(s.fromUserId) ??
          formatPossiblyDeletedUser(s.fromUserId, undefined),
        toUserId: s.toUserId,
        toUser:
          userViewMap.get(s.toUserId) ??
          formatPossiblyDeletedUser(s.toUserId, undefined),
        amount: s.amount,
      }),
    );

    const settlementViews: SettlementView[] = settlements.map((st) => {
      const dUid = normalizeUuid(st.debtorId);
      const cUid = normalizeUuid(st.creditorId);
      return {
        id: st.id,
        groupId: st.groupId,
        tripId: st.tripId ?? null,
        debtorId: st.debtorId,
        debtor:
          userViewMap.get(dUid) ?? formatPossiblyDeletedUser(dUid, undefined),
        creditorId: st.creditorId,
        creditor:
          userViewMap.get(cUid) ?? formatPossiblyDeletedUser(cUid, undefined),
        createdByUserId: st.createdByUserId,
        amount: st.amount,
        currency: st.currency,
        notes: st.notes ?? null,
        settledAt: st.settledAt,
      };
    });

    return {
      totalSpent,
      totalOutstandingDebt,
      zeroSumVerified: netSum === 0n,
      balanceByUser,
      balances,
      suggestedTransactions,
      settlements: settlementViews,
    };
  }

  /**
   * Used inside `GroupsService.removeMember` transaction (after `_lockGroup`)
   * to enforce `409 MEMBER_HAS_UNSETTLED_BALANCE` whenever `netBalance !== 0n`.
   */
  async getMemberNetBalanceInTx(
    tx: Prisma.TransactionClient,
    rawGroupId: string,
    rawTargetUserId: string,
  ): Promise<bigint> {
    const groupId = normalizeUuid(rawGroupId);
    const targetUid = normalizeUuid(rawTargetUserId);

    const expenses = await tx.expense.findMany({
      where: { groupId, deletedAt: null },
      include: { splits: true },
    });
    const settlements = await tx.settlement.findMany({
      where: { groupId },
    });

    let paid = 0n;
    let owed = 0n;
    let outSt = 0n;
    let inSt = 0n;

    for (const exp of expenses) {
      if (normalizeUuid(exp.paidByUserId) === targetUid) {
        paid += BigInt(exp.amount);
      }
      for (const sp of exp.splits) {
        if (normalizeUuid(sp.userId) === targetUid) {
          owed += BigInt(sp.shareAmount);
        }
      }
    }
    for (const st of settlements) {
      if (normalizeUuid(st.debtorId) === targetUid) {
        outSt += BigInt(st.amount);
      }
      if (normalizeUuid(st.creditorId) === targetUid) {
        inSt += BigInt(st.amount);
      }
    }

    return paid - owed + outSt - inSt;
  }

  private _formatExpenseView(
    exp: {
      id: string;
      groupId: string;
      tripId: string | null;
      title: string;
      amount: number;
      currency: string;
      category: ExpenseCategory;
      splitType: SplitType;
      expenseDate: Date;
      notes: string | null;
      paidByUserId: string;
      createdByUserId: string;
      createdAt: Date;
      splits: Array<{ id: string; userId: string; shareAmount: number }>;
    },
    ctx: {
      actorId: string;
      isTripOwner: boolean;
      myGroupRole: GroupRole;
      activeMemberIds: Set<string>;
    },
    hasSettlements: boolean,
    userViewMap: Map<string, SafeBuddyPeerView>,
  ): ExpenseView {
    const payerUid = normalizeUuid(exp.paidByUserId);
    const creatorUid = normalizeUuid(exp.createdByUserId);
    const hasFormerMember =
      !ctx.activeMemberIds.has(payerUid) ||
      exp.splits.some((sp) => !ctx.activeMemberIds.has(normalizeUuid(sp.userId)));

    const canDelete =
      !hasSettlements &&
      !hasFormerMember &&
      (ctx.isTripOwner ||
        ctx.myGroupRole === GROUP_ROLES.ADMIN ||
        creatorUid === ctx.actorId);

    return {
      id: exp.id,
      groupId: exp.groupId,
      tripId: exp.tripId ?? null,
      title: exp.title,
      amount: exp.amount,
      currency: exp.currency,
      category: exp.category,
      splitType: exp.splitType,
      expenseDate: exp.expenseDate,
      notes: exp.notes ?? null,
      paidByUserId: exp.paidByUserId,
      paidBy:
        userViewMap.get(payerUid) ??
        formatPossiblyDeletedUser(payerUid, undefined),
      createdByUserId: exp.createdByUserId,
      createdBy:
        userViewMap.get(creatorUid) ??
        formatPossiblyDeletedUser(creatorUid, undefined),
      createdAt: exp.createdAt,
      canDelete,
      splits: exp.splits.map((sp) => {
        const sUid = normalizeUuid(sp.userId);
        return {
          id: sp.id,
          userId: sp.userId,
          shareAmount: sp.shareAmount,
          user:
            userViewMap.get(sUid) ?? formatPossiblyDeletedUser(sUid, undefined),
        };
      }),
    };
  }

  async createExpense(
    rawGroupId: string,
    rawActorId: string,
    dto: CreateExpenseDto,
    idempotencyKey?: string,
  ): Promise<ExpenseView> {
    const groupId = normalizeUuid(rawGroupId);
    const actorId = normalizeUuid(rawActorId);
    const rawReqId = dto.clientRequestId?.trim() || idempotencyKey?.trim();
    const effectiveClientRequestId =
      rawReqId && rawReqId.length > 0 ? rawReqId.slice(0, 128) : undefined;

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveGroupContext(tx, groupId, actorId);

      const paidByUserId = dto.paidByUserId
        ? normalizeUuid(dto.paidByUserId)
        : actorId;
      const splitType = dto.splitType ?? SplitType.EQUAL;
      const category = dto.category ?? ExpenseCategory.OTHER;

      if (effectiveClientRequestId) {
        const existing = await tx.expense.findFirst({
          where: {
            groupId: ctx.groupId,
            clientRequestId: effectiveClientRequestId,
          },
          include: { splits: true },
        });
        if (existing) {
          const normalizedNotes = dto.notes?.trim() ?? null;
          if (
            existing.deletedAt !== null ||
            existing.amount !== dto.amount ||
            normalizeUuid(existing.paidByUserId) !== paidByUserId ||
            existing.splitType !== splitType ||
            existing.category !== category ||
            existing.title !== dto.title.trim() ||
            (existing.notes ?? null) !== normalizedNotes
          ) {
            throw new ConflictException({
              errorCode: GROUP_ERROR_CODES.IDEMPOTENCY_PAYLOAD_MISMATCH,
              message:
                'clientRequestId đã được sử dụng cho một khoản chi khác trong nhóm',
            });
          }
          const settlementCount = await tx.settlement.count({
            where: { groupId: ctx.groupId },
          });
          const uids = new Set<string>([
            existing.paidByUserId,
            existing.createdByUserId,
            ...existing.splits.map((s) => s.userId),
          ]);
          const userMap = await this._hydrateUserMap(
            tx,
            uids,
            ctx.allMemberMap,
          );
          return this._formatExpenseView(
            existing,
            ctx,
            settlementCount > 0,
            userMap,
          );
        }
      }

      if (!ctx.activeMemberIds.has(paidByUserId)) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.EXPENSE_INVALID_PARTICIPANT,
          message: 'Người trả tiền phải là thành viên đang hoạt động trong nhóm',
        });
      }

      let splitsToCreate: Array<{ userId: string; shareAmount: number }> = [];

      if (splitType === SplitType.EQUAL) {
        const rawParticipants =
          dto.participantIds && dto.participantIds.length > 0
            ? dto.participantIds
            : Array.from(ctx.activeMemberIds);

        for (const pId of rawParticipants) {
          if (!ctx.activeMemberIds.has(normalizeUuid(pId))) {
            throw new BadRequestException({
              errorCode: GROUP_ERROR_CODES.EXPENSE_INVALID_PARTICIPANT,
              message:
                'Tất cả thành viên được chia chi phí phải thuộc nhóm đồng hành',
            });
          }
        }
        splitsToCreate = computeDeterministicEqualSplits(
          dto.amount,
          rawParticipants,
        );
      } else {
        if (!dto.customSplits || dto.customSplits.length === 0) {
          throw new BadRequestException({
            errorCode: 'VALIDATION_ERROR',
            message: 'customSplits là bắt buộc khi chọn chia tùy chỉnh (CUSTOM)',
          });
        }
        const seenUsers = new Set<string>();
        let sum = 0n;
        for (const entry of dto.customSplits) {
          const uid = normalizeUuid(entry.userId);
          if (seenUsers.has(uid)) {
            throw new BadRequestException({
              errorCode: 'VALIDATION_ERROR',
              message: 'Danh sách customSplits có thành viên bị trùng lặp',
            });
          }
          seenUsers.add(uid);
          if (!ctx.activeMemberIds.has(uid)) {
            throw new BadRequestException({
              errorCode: GROUP_ERROR_CODES.EXPENSE_INVALID_PARTICIPANT,
              message:
                'Tất cả thành viên được chia chi phí phải thuộc nhóm đồng hành',
            });
          }
          sum += BigInt(entry.shareAmount);
          if (entry.shareAmount > 0) {
            splitsToCreate.push({
              userId: uid,
              shareAmount: entry.shareAmount,
            });
          }
        }

        if (sum !== BigInt(dto.amount) || splitsToCreate.length === 0) {
          throw new BadRequestException({
            errorCode: GROUP_ERROR_CODES.EXPENSE_SPLIT_SUM_MISMATCH,
            message: 'Tổng các phần chia tùy chỉnh phải khớp chính xác tổng khoản chi',
          });
        }

        splitsToCreate.sort((a, b) =>
          a.userId < b.userId ? -1 : a.userId > b.userId ? 1 : 0,
        );
      }

      const created = await tx.expense.create({
        data: {
          groupId: ctx.groupId,
          tripId: ctx.linkedTripId,
          paidByUserId,
          createdByUserId: actorId,
          ...(effectiveClientRequestId
            ? { clientRequestId: effectiveClientRequestId }
            : {}),
          title: dto.title.trim(),
          amount: dto.amount,
          currency: 'VND',
          category,
          splitType,
          expenseDate: dto.expenseDate ? new Date(dto.expenseDate) : new Date(),
          notes: dto.notes?.trim() ?? null,
          splits: {
            create: splitsToCreate.map((sp) => ({
              userId: sp.userId,
              shareAmount: sp.shareAmount,
            })),
          },
        },
        include: { splits: true },
      });

      const settlementCount = await tx.settlement.count({
        where: { groupId: ctx.groupId },
      });
      const uids = new Set<string>([
        created.paidByUserId,
        created.createdByUserId,
        ...created.splits.map((s) => s.userId),
      ]);
      const userMap = await this._hydrateUserMap(tx, uids, ctx.allMemberMap);

      return this._formatExpenseView(
        created,
        ctx,
        settlementCount > 0,
        userMap,
      );
    });
  }

  async listExpenses(
    rawGroupId: string,
    rawActorId: string,
  ): Promise<ExpenseListView> {
    const ctx = await this._resolveGroupContext(
      this.prisma,
      rawGroupId,
      rawActorId,
    );

    const expenses = await this.prisma.expense.findMany({
      where: { groupId: ctx.groupId, deletedAt: null },
      orderBy: [{ expenseDate: 'desc' }, { createdAt: 'desc' }],
      include: { splits: true },
    });
    const settlementCount = await this.prisma.settlement.count({
      where: { groupId: ctx.groupId },
    });

    const uids = new Set<string>();
    let totalSpent = 0n;
    for (const exp of expenses) {
      totalSpent += BigInt(exp.amount);
      uids.add(exp.paidByUserId);
      uids.add(exp.createdByUserId);
      for (const sp of exp.splits) {
        uids.add(sp.userId);
      }
    }
    const userMap = await this._hydrateUserMap(
      this.prisma,
      uids,
      ctx.allMemberMap,
    );
    const hasSettlements = settlementCount > 0;

    return {
      groupId: ctx.groupId,
      currency: 'VND',
      hasSettlements,
      totalSpent: toSafeNumber(totalSpent),
      expenseCount: expenses.length,
      expenses: expenses.map((exp) =>
        this._formatExpenseView(exp, ctx, hasSettlements, userMap),
      ),
    };
  }

  async getExpense(
    rawGroupId: string,
    rawExpenseId: string,
    rawActorId: string,
  ): Promise<ExpenseView> {
    const ctx = await this._resolveGroupContext(
      this.prisma,
      rawGroupId,
      rawActorId,
    );
    const expenseId = normalizeUuid(rawExpenseId);

    const exp = await this.prisma.expense.findFirst({
      where: { id: expenseId, groupId: ctx.groupId, deletedAt: null },
      include: { splits: true },
    });
    if (!exp) {
      throw new NotFoundException({
        errorCode: GROUP_ERROR_CODES.EXPENSE_NOT_FOUND,
        message: 'Khoản chi không tồn tại trong nhóm',
      });
    }

    const settlementCount = await this.prisma.settlement.count({
      where: { groupId: ctx.groupId },
    });
    const uids = new Set<string>([
      exp.paidByUserId,
      exp.createdByUserId,
      ...exp.splits.map((s) => s.userId),
    ]);
    const userMap = await this._hydrateUserMap(
      this.prisma,
      uids,
      ctx.allMemberMap,
    );

    return this._formatExpenseView(exp, ctx, settlementCount > 0, userMap);
  }

  async deleteExpense(
    rawGroupId: string,
    rawExpenseId: string,
    rawActorId: string,
  ): Promise<{ deleted: boolean; groupId: string; expenseId: string }> {
    const groupId = normalizeUuid(rawGroupId);
    const expenseId = normalizeUuid(rawExpenseId);
    const actorId = normalizeUuid(rawActorId);

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveGroupContext(tx, groupId, actorId);

      const exp = await tx.expense.findFirst({
        where: { id: expenseId, groupId: ctx.groupId, deletedAt: null },
        include: { splits: true },
      });
      if (!exp) {
        throw new NotFoundException({
          errorCode: GROUP_ERROR_CODES.EXPENSE_NOT_FOUND,
          message: 'Khoản chi không tồn tại trong nhóm',
        });
      }

      const canDeleteByRole =
        ctx.isTripOwner ||
        ctx.myGroupRole === GROUP_ROLES.ADMIN ||
        normalizeUuid(exp.createdByUserId) === actorId;
      if (!canDeleteByRole) {
        throw new ForbiddenException({
          errorCode: GROUP_ERROR_CODES.EXPENSE_DELETE_FORBIDDEN,
          message: 'Thành viên chỉ có quyền xóa khoản chi do chính mình tạo',
        });
      }

      const settlementCount = await tx.settlement.count({
        where: { groupId: ctx.groupId },
      });
      if (settlementCount > 0) {
        throw new ConflictException({
          errorCode: GROUP_ERROR_CODES.EXPENSE_LOCKED_BY_SETTLEMENT,
          message:
            'Nhóm đã phát sinh bản ghi đối soát nên không thể xóa khoản chi cũ; vui lòng tạo khoản chi bù trừ nếu cần điều chỉnh',
        });
      }

      const payerUid = normalizeUuid(exp.paidByUserId);
      const hasFormerMember =
        !ctx.activeMemberIds.has(payerUid) ||
        exp.splits.some(
          (sp) => !ctx.activeMemberIds.has(normalizeUuid(sp.userId)),
        );
      if (hasFormerMember) {
        throw new ConflictException({
          errorCode: GROUP_ERROR_CODES.EXPENSE_HAS_FORMER_MEMBER,
          message: 'Không thể xóa khoản chi có liên quan đến thành viên đã rời khỏi nhóm',
        });
      }

      await tx.expense.update({
        where: { id: exp.id },
        data: { deletedAt: new Date() },
      });

      return {
        deleted: true,
        groupId: ctx.groupId,
        expenseId: exp.id,
      };
    });
  }

  async getSettlementPlan(
    rawGroupId: string,
    rawActorId: string,
  ): Promise<SettlementPlanView> {
    const ctx = await this._resolveGroupContext(
      this.prisma,
      rawGroupId,
      rawActorId,
    );
    const ledger = await this._computeLedger(
      this.prisma,
      ctx.groupId,
      ctx.activeMemberIds,
      ctx.allMemberMap,
    );

    return {
      groupId: ctx.groupId,
      currency: 'VND',
      totalSpent: toSafeNumber(ledger.totalSpent),
      totalOutstandingDebt: toSafeNumber(ledger.totalOutstandingDebt),
      zeroSumVerified: ledger.zeroSumVerified,
      balances: ledger.balances,
      suggestedTransactions: ledger.suggestedTransactions,
      settlements: ledger.settlements,
    };
  }

  async createSettlement(
    rawGroupId: string,
    rawActorId: string,
    dto: CreateSettlementDto,
    idempotencyKey?: string,
  ): Promise<{
    settlement: SettlementView;
    updatedBalances: MemberBalanceView[];
  }> {
    const groupId = normalizeUuid(rawGroupId);
    const actorId = normalizeUuid(rawActorId);
    const debtorId = normalizeUuid(dto.debtorId);
    const creditorId = normalizeUuid(dto.creditorId);
    const rawReqId = dto.clientRequestId?.trim() || idempotencyKey?.trim();
    const effectiveClientRequestId =
      rawReqId && rawReqId.length > 0 ? rawReqId.slice(0, 128) : undefined;

    return this.prisma.$transaction(async (tx) => {
      await this._lockGroup(tx, groupId);
      const ctx = await this._resolveGroupContext(tx, groupId, actorId);

      // STRICT INVARIANT (Approved Decision #6 — Checked BEFORE idempotency & payload checks):
      // If actor == debtor -> ALWAYS 403 SETTLEMENT_FORBIDDEN, including admin AND including retry!
      if (actorId === debtorId) {
        throw new ForbiddenException({
          errorCode: GROUP_ERROR_CODES.SETTLEMENT_FORBIDDEN,
          message:
            'Người nợ không được tự xác nhận khoản nợ của chính mình, kể cả khi là quản trị viên nhóm',
        });
      }

      const canConfirm =
        actorId === creditorId || ctx.myGroupRole === GROUP_ROLES.ADMIN;
      if (!canConfirm) {
        throw new ForbiddenException({
          errorCode: GROUP_ERROR_CODES.SETTLEMENT_FORBIDDEN,
          message:
            'Chỉ người nhận tiền hoặc quản trị viên nhóm (không phải người nợ) mới có quyền xác nhận đã nhận tiền',
        });
      }

      if (debtorId === creditorId) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.SETTLEMENT_SAME_USER,
          message: 'Người trả và người nhận không được trùng nhau',
        });
      }

      if (effectiveClientRequestId) {
        const existing = await tx.settlement.findFirst({
          where: {
            groupId: ctx.groupId,
            clientRequestId: effectiveClientRequestId,
          },
        });
        if (existing) {
          const normalizedNotes = dto.notes?.trim() ?? null;
          if (
            normalizeUuid(existing.debtorId) !== debtorId ||
            normalizeUuid(existing.creditorId) !== creditorId ||
            existing.amount !== dto.amount ||
            (existing.notes ?? null) !== normalizedNotes
          ) {
            throw new ConflictException({
              errorCode: GROUP_ERROR_CODES.IDEMPOTENCY_PAYLOAD_MISMATCH,
              message:
                'clientRequestId đã được sử dụng cho một giao dịch đối soát khác',
            });
          }
          const currentLedger = await this._computeLedger(
            tx,
            ctx.groupId,
            ctx.activeMemberIds,
            ctx.allMemberMap,
          );
          const matchedView = currentLedger.settlements.find(
            (s) => s.id === existing.id,
          )!;
          return {
            settlement: matchedView,
            updatedBalances: currentLedger.balances,
          };
        }
      }

      if (!ctx.allMemberMap.has(debtorId) || !ctx.allMemberMap.has(creditorId)) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.SETTLEMENT_INVALID_PARTY,
          message: 'Người trả và người nhận phải thuộc danh sách thành viên nhóm',
        });
      }

      const beforeLedger = await this._computeLedger(
        tx,
        ctx.groupId,
        ctx.activeMemberIds,
        ctx.allMemberMap,
      );
      const debtorBalance = beforeLedger.balanceByUser.get(debtorId) ?? 0n;
      const creditorBalance = beforeLedger.balanceByUser.get(creditorId) ?? 0n;

      if (debtorBalance >= 0n || creditorBalance <= 0n) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.SETTLEMENT_AMOUNT_EXCEEDS_DEBT,
          message:
            'Không có khoản công nợ hợp lệ cần tất toán giữa hai thành viên này',
        });
      }

      const maxSettleable =
        -debtorBalance < creditorBalance ? -debtorBalance : creditorBalance;
      if (BigInt(dto.amount) > maxSettleable) {
        throw new BadRequestException({
          errorCode: GROUP_ERROR_CODES.SETTLEMENT_AMOUNT_EXCEEDS_DEBT,
          message: `Số tiền đối soát vượt quá dư nợ tối đa có thể tất toán (${maxSettleable.toString()} VND)`,
        });
      }

      const created = await tx.settlement.create({
        data: {
          groupId: ctx.groupId,
          tripId: ctx.linkedTripId,
          debtorId,
          creditorId,
          createdByUserId: actorId,
          ...(effectiveClientRequestId
            ? { clientRequestId: effectiveClientRequestId }
            : {}),
          amount: dto.amount,
          currency: 'VND',
          notes: dto.notes?.trim() ?? null,
          settledAt: dto.settledAt ? new Date(dto.settledAt) : new Date(),
        },
      });

      const afterLedger = await this._computeLedger(
        tx,
        ctx.groupId,
        ctx.activeMemberIds,
        ctx.allMemberMap,
      );
      const createdView = afterLedger.settlements.find(
        (s) => s.id === created.id,
      )!;

      return {
        settlement: createdView,
        updatedBalances: afterLedger.balances,
      };
    });
  }
}
