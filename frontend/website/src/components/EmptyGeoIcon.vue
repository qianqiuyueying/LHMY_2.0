<template>
  <div class="geo" aria-hidden="true">
    <div class="dot dot-a" />
    <div class="dot dot-b" />
    <div class="pill" />
    <div class="card" />
  </div>
</template>

<style scoped>
.geo {
  width: 72px;
  height: 72px;
  position: relative;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(20, 184, 166, 0.12), rgba(15, 118, 110, 0.06));
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.dot {
  position: absolute;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.9), rgba(45, 212, 191, 0.9));
  opacity: 0.9;
}
.dot-a {
  width: 10px;
  height: 10px;
  left: 14px;
  top: 16px;
}
.dot-b {
  width: 8px;
  height: 8px;
  right: 16px;
  top: 20px;
  opacity: 0.65;
}

.pill {
  position: absolute;
  left: 14px;
  right: 14px;
  top: 34px;
  height: 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
}

.card {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 14px;
  height: 18px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.06);
  border: 1px solid rgba(15, 23, 42, 0.04);
}
</style>


