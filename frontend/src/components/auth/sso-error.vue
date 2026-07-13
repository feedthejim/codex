<template>
  <v-container class="ssoErrorContainer">
    <v-card class="ssoErrorCard" max-width="22em">
      <v-card-title>SSO Login Failed</v-card-title>
      <v-card-text>
        <p class="codexFormError">
          {{ message }}
        </p>
        <SsoLoginButton v-if="canRetry" class="ssoRetry" />
        <v-btn block variant="text" @click="goHome"> Use local login </v-btn>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script>
import { mapWritableState } from "pinia";

import SsoLoginButton from "@/components/auth/sso-login-button.vue";
import { useAuthStore } from "@/stores/auth";

// Error codes emitted by the backend adapter (codex/oidc.py); anything
// else was collapsed to server_error before the redirect.
const MESSAGES = Object.freeze({
  access_denied: "The identity provider denied the login request.",
  signup_disabled:
    "Automatic account creation is disabled. Ask an administrator to create your account first.",
  email_exists:
    "A local account with this email address already exists. Log in with your local password instead, or ask an administrator to link the accounts.",
  server_error:
    "The identity provider could not be reached or returned an error. Try again later.",
});
// Retrying immediately can't succeed for these; hide the retry button.
const NO_RETRY = Object.freeze(new Set(["signup_disabled", "email_exists"]));

export default {
  name: "SsoError",
  components: {
    SsoLoginButton,
  },
  computed: {
    ...mapWritableState(useAuthStore, ["showLoginDialog"]),
    error() {
      return this.$route.query.error || "server_error";
    },
    message() {
      return MESSAGES[this.error] || MESSAGES.server_error;
    },
    canRetry() {
      return !NO_RETRY.has(this.error);
    },
  },
  methods: {
    goHome() {
      this.showLoginDialog = true;
      this.$router.push({ name: "home" });
    },
  },
};
</script>

<style scoped lang="scss">
.ssoErrorContainer {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 4em;
}

.ssoErrorCard {
  padding: 1em;
}

.codexFormError {
  color: rgb(var(--v-theme-error));
  text-align: center;
  margin-bottom: 1.5em;
}

.ssoRetry {
  margin-bottom: 0.75em;
}
</style>
