"use strict";
// BootBridge device page: shows /api/state and drives the four actions.
// All decisions are made on the device; this page only displays them.
(function () {
  const $ = (id) => document.getElementById(id);
  const BOARD = { A: "HW-A", B: "HW-B", C: "HW-C", D: "HW-D", NX54: "NX54 VER.A" };
  let state = null;
  let busy = false;
  let done = false;	// install or return finished: only reboot is left

  async function api(path, post) {
    const r = await fetch(path, post ? { method: "POST", headers: { "X-BootBridge": "1" } } : {});
    if (!r.ok) {
      const state = await r.json().catch(() => null);
      if (state && state.schema === "bb-state-v1") return state;
      throw new Error("HTTP " + r.status);
    }
    return r.json();
  }

  function setStep(n) {
    document.querySelectorAll(".bk-nav li").forEach((li) => {
      const s = Number(li.dataset.step);
      li.classList.toggle("bk-active", s === n);
      li.classList.toggle("bk-done", s < n);
    });
  }

  function notice(title, copy) {
    $("notice").hidden = !title;
    $("notice-title").textContent = title || "";
    $("notice-copy").textContent = copy || "";
  }

  function tech(s) {
    const f = s.facts || {}, n = f.nand || {}, d = s.decision || {}, r = s.oem_return || {};
    const rows = [
      ["规则集", s.rule_set || "无"], ["规则包", s.pack],
      ["分区布局", f.layout || "未读到"], ["SBL1 SHA-256", f.sbl1_sha256 || "未读到"],
      ["启动路由", f.route || "未读到"], ["machid", f.machid || "未读到"],
      ["闪存", (n.model || "?") + " (" + (n.id || "?") + ")，ECC " + (n.ecc || "?")],
      ["原厂产品名", (f.env || {}).productname || "未读到"],
      ["条码前 10 位", (f.env || {}).item_code || "未读到"],
      ["判断结果", d.code + (d.detail ? "：" + d.detail : "")],
      ["U-Boot 候选", d.candidate || "无"],
      ["回原厂检查", r.code + "（原厂槽 0x" + Number(r.oem_offset || 0).toString(16) + "，" + r.oem_slot + "）"],
      ["备份", s.backup.ready ? s.backup.bytes + " 字节，SHA-256 " + s.backup.sha256 : "未生成"],
      ["上次操作", s.last.action ? s.last.action + " → " + s.last.code : "无"],
    ];
    if (f.ecc_evidence && f.ecc_evidence.sampled) {
      const names = ["SBL1", "APPSBL", "APPSBL_1", "BOOTCONFIG", "BOOTCONFIG1"];
      rows.push(["nand_evidence", d.nand_evidence || "refused"]);
      (f.ecc_evidence.parts || []).forEach((p, i) => rows.push([names[i],
        "failed " + p.failed + "，corrected " + p.corrected + "（上限 8），非擦除页 " + p.non_ff]));
    }
    const dl = $("tech");
    dl.textContent = "";
    rows.forEach(([k, v]) => {
      const dt = document.createElement("dt"), dd = document.createElement("dd");
      dt.textContent = k;
      dd.textContent = String(v);
      dl.append(dt, dd);
    });
  }

  function render(s) {
    // Returning to OEM is independent of every other feature: only an operation in flight blocks it.
    $("return-button").disabled = busy;
    state = s;
    const d = s.decision, r = s.oem_return, b = s.backup, last = s.last;
    const canReturn = r.code === "ready" || r.code === "already_oem";
    const matched = d.code === "ok";

    $("device").hidden = false;
    $("device-name").textContent = ((s.facts.env || {}).productname || "未知机型") +
      (matched ? " · " + (BOARD[d.board] || d.board) : "");
    $("device-sub").textContent = d.nand_evidence === "experimental"
      ? "闪存型号未登记，按实测 ECC 放行（实验性）。安装前请务必生成并下载完整备份。"
      : matched ? "将安装 " + d.candidate : d.message;
    $("backup").hidden = !matched;
    $("backup-link").hidden = !b.ready;
    $("backup-copy").textContent = b.ready
      ? "备份已生成（" + Math.round(b.bytes / 1048576) + " MiB）。请下载保存到电脑，不要公开分享。" +
        (b.unreadable_blocks ? " 注意：有 " + b.unreadable_blocks + " 个块读不出，已用 0xFF 代替。" : "")
      : "安装前必须先生成备份。备份含设备私有数据，请保存在自己的电脑上，不要公开分享。";
    notice("", "");

    const main = $("main-button");
    if (last.action === "install" && last.code === "done" || last.action === "return" &&
        (last.code === "done" || last.code === "already_oem")) {
      done = true;
      setStep(4);
      $("kicker").textContent = "第 4 步 · 重启";
      $("title").textContent = last.action === "install" ? "U-Boot 安装完成" : "已切换到原厂系统";
      $("badge").textContent = "已完成";
      $("message").textContent = last.message + "。点“重启”后，路由器将进入原厂系统。";
      main.textContent = "重启";
      main.disabled = busy;
      main.onclick = reboot;
    } else if (!matched) {
      setStep(1);
      $("kicker").textContent = "第 1 步 · 检查设备";
      $("title").textContent = "这台设备暂不能安装";
      $("badge").textContent = "不能安装";
      $("message").textContent = d.message + "。可以返回原厂系统，或下载诊断信息反馈给作者。";
      main.textContent = "不能安装";
      main.disabled = true;
    } else if (!b.ready) {
      setStep(2);
      $("kicker").textContent = "第 2 步 · 备份";
      $("title").textContent = "检查通过，先生成备份";
      $("badge").textContent = "可以安装";
      $("message").textContent = "已识别为 " + (BOARD[d.board] || d.board) + "。安装前需要先在设备上生成恢复备份。";
      main.textContent = "生成备份";
      main.disabled = busy;
      main.onclick = () => run("/api/backup", "正在生成备份，包含系统槽时可能需要数分钟…");
    } else if (b.full && !b.downloaded) {
      setStep(2);
      $("title").textContent = "先下载完整备份";
      $("message").textContent = "请点击“下载备份”，保存后核对 ZIP 和 SHA-256，再安装 U-Boot。";
      main.textContent = "请先下载备份";
      main.disabled = true;
    } else {
      setStep(3);
      $("kicker").textContent = "第 3 步 · 安装 U-Boot";
      $("title").textContent = "可以安装";
      $("badge").textContent = "可以安装";
      $("message").textContent = "将写入两份 U-Boot 并逐一读回校验，完成后切换到原厂系统。";
      main.textContent = "安装 U-Boot";
      main.disabled = busy;
      main.onclick = () => confirmThen("确认安装 U-Boot？",
        "将写入 " + d.candidate + "。安装过程中不要断电。",
        () => run("/api/install", "正在写入 U-Boot，请不要断电…"));
    }
    if (last.code && !done && last.code !== "ok" && last.code !== "ready")
      notice("上次操作没有完成", last.message);
    if (!canReturn) $("note").textContent = "当前不能返回原厂：" + r.message;
    else $("note").textContent = "随时可以返回原厂系统，也可以长按路由器的 Mesh/WPS 键 3 秒";
    tech(s);
  }

  function confirmThen(title, copy, action) {
    $("confirm-title").textContent = title;
    $("confirm-copy").textContent = copy;
    $("confirm").hidden = false;
    $("confirm-no").onclick = () => { $("confirm").hidden = true; };
    $("confirm-yes").onclick = () => { $("confirm").hidden = true; action(); };
  }

  async function run(path, waiting) {
    busy = true;
    $("message").textContent = waiting;
    $("main-button").disabled = true;
    $("return-button").disabled = true;
    try {
      render(await api(path, true));
    } catch (e) {
      notice("与设备通信失败", String(e.message || e) + "。请刷新页面查看设备状态。");
    } finally {
      busy = false;
      if (state) render(state);
    }
  }

  async function reboot() {
    busy = true;
    try {
      const reply = await api("/api/reboot", true);
      if (!reply.last || reply.last.code !== "ok") {
        busy = false;
        render(reply);
        return;
      }
    } catch (e) { /* the reboot response may be interrupted */ }
    $("title").textContent = "正在重启";
    $("message").textContent = "约 1 分钟后路由器进入原厂系统。此页面不会再更新。";
    $("main-button").disabled = true;
  }

  $("return-button").onclick = () => confirmThen("返回原厂系统？",
    "只修改启动配置，不改动原厂系统和 U-Boot。之后点“重启”即进入原厂系统。",
    () => run("/api/return", "正在切换启动配置…"));
  $("diag-button").onclick = () => { location.href = "/api/diagnostics"; };

  $("backup-link").onclick = () => {
    // The service handles requests sequentially: this state request completes
    // after the ZIP transfer and exposes whether every byte was sent.
    setTimeout(() => api("/api/state").then(render).catch(() => {}), 500);
  };

  api("/api/state").then(render).catch((e) => notice("无法读取设备状态", String(e.message || e)));
})();
