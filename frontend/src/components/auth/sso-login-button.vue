<template>
  <v-btn
    v-if="adminFlags.oidcEnabled"
    id="ssoLoginButton"
    block
    color="primary"
    :prepend-icon="mdiOpenid"
    @click="loginSSO"
  >
    Login with {{ adminFlags.oidcProviderName }}
  </v-btn>
</template>

<script>
import { mdiOpenid } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

export default {
  name: "SsoLoginButton",
  data() {
    return {
      mdiOpenid,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["adminFlags"]),
  },
  methods: {
    ...mapActions(useAuthStore, ["loginSSO"]),
  },
};
</script>
