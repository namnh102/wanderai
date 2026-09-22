import 'package:flutter_riverpod/flutter_riverpod.dart';

class AuthState {
  final bool isLoggedIn;
  AuthState({this.isLoggedIn = false});
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(AuthState(isLoggedIn: false));

  void login(String email, String password) {
    state = AuthState(isLoggedIn: true);
  }

  void register(String name, String email, String password) {
    state = AuthState(isLoggedIn: true);
  }

  void logout() {
    state = AuthState(isLoggedIn: false);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});
