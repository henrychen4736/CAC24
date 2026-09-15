/// Friendly copy for FirebaseAuthException codes.
String authErrorMessage(String code) => switch (code) {
      'invalid-credential' ||
      'wrong-password' ||
      'user-not-found' ||
      'INVALID_LOGIN_CREDENTIALS' =>
        'That email and password don’t match. Check them and try again.',
      'invalid-email' => 'That doesn’t look like a valid email address.',
      'user-disabled' => 'This account has been disabled. Contact support for help.',
      'email-already-in-use' => 'An account already exists for that email. Try signing in instead.',
      'weak-password' => 'Choose a stronger password (at least 6 characters).',
      'too-many-requests' => 'Too many attempts. Wait a few minutes and try again.',
      'network-request-failed' => 'No internet connection. Check your network and try again.',
      'operation-not-allowed' => 'Email sign-in isn’t enabled for this app yet.',
      'requires-recent-login' => 'For your security, please enter your password again.',
      _ => 'Something went wrong. Please try again.',
    };
