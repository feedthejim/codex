<!--
  A titled admin block: header (h3 + optional right-aligned actions), an
  optional one-line hint, then its body. The unified replacement for the
  hand-written .adminGroup / .adminGroupHeader / <h3> markup. See DESIGN.md §4.

  The `sub` variant nests inside another AdminSection: a smaller overline
  h4 title and an indented left rule make the subordination visible (see
  the Auth tab's OIDC block).
-->
<template>
  <section class="adminGroup" :class="{ adminSubGroup: sub }">
    <header v-if="title || $slots.actions" class="adminGroupHeader">
      <component :is="sub ? 'h4' : 'h3'">{{ title }}</component>
      <slot name="actions" />
    </header>
    <p v-if="hint || $slots.hint" class="adminHint">
      <slot name="hint">{{ hint }}</slot>
    </p>
    <slot />
  </section>
</template>

<script>
export default {
  name: "AdminSection",
  props: {
    title: { type: String, default: "" },
    hint: { type: String, default: "" },
    sub: { type: Boolean, default: false },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
</style>
