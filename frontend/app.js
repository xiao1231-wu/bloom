import * as THREE from "./vendor/three/three.module.js";

let storedToken = localStorage.getItem("md_token") || "";
let storedUser = null;
if (storedToken) {
  try {
    storedUser = JSON.parse(localStorage.getItem("md_user") || "null");
    if (!storedUser || typeof storedUser.id !== "number") throw new Error("Invalid saved user");
  } catch {
    storedToken = "";
    localStorage.removeItem("md_user");
    localStorage.removeItem("md_token");
  }
}
const state = {
  user: storedUser,
  token: storedToken,
  styles: [],
  posts: [],
  favorites: [],
  stores: [],
  activeView: "home",
  selectedStyle: null,
  handImage: "",
  userGender: localStorage.getItem("md_gender") || "female",
  profile: { skin_tone: "自然黄皮", hand_shape: "修长手", nail_shape: "方圆形", scene: "日常", target_length: "中", maintenance_preference: "中", decoration_level: "轻量", budget_range: "不限", nail_conditions: ["无明显困扰"], gender: localStorage.getItem("md_gender") || "female" },
  matchResult: null,
  recommendationPlan: storedUser?.profile?.latest_recommendation_plan || null,
  communityFilter: "全部",
  tutorialRecommendations: [],
};

const app = document.querySelector("#app");
let renderQueue = Promise.resolve();
const HAND_LANDMARKER_MODULE = "./vendor/mediapipe/vision_bundle.mjs";
const HAND_LANDMARKER_WASM = "./vendor/mediapipe/wasm";
const HAND_LANDMARKER_MODEL = "./vendor/mediapipe/hand_landmarker.task";
const tryonRuntime = {
  mode: "idle",
  stream: null,
  frameRequest: 0,
  session: 0,
  landmarker: null,
  landmarkerPromise: null,
  runningMode: "",
  lastVideoTime: -1,
  lastDetectionAt: 0,
  lastHandSeenAt: 0,
  lastHands: [],
  smoothedHands: new Map(),
  staticImage: null,
  staticHands: [],
  staticFallback: false,
  hasFrame: false,
  detectionFailed: false,
  resizeObserver: null,
};
const api = async (url, options = {}) => {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(url, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && state.token) {
      state.user = null; state.token = ""; state.favorites = [];
      localStorage.removeItem("md_user"); localStorage.removeItem("md_token");
    }
    throw new Error(data.error || "\u8bf7\u6c42\u5931\u8d25");
  }
  return data;
};
const escapeHtml = (text = "") => text.replace(/[&<>"']/g, ch => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;" }[ch]));
function avatarContent(name = "", avatarUrl = "") {
  const initial = escapeHtml((name || "美").slice(0, 1).toUpperCase());
  if (!avatarUrl) return initial;
  return `<img src="${escapeHtml(String(avatarUrl))}" alt="${escapeHtml(name || "用户")}的头像">`;
}
function toast(message) { const el = document.createElement("div"); el.className = "toast"; el.textContent = message; document.querySelector("#toast-root").append(el); setTimeout(() => el.remove(), 2600); }
function icon(name, size = 16) { return `<i data-lucide="${name}" width="${size}" height="${size}"></i>`; }
function renderIcons() { window.lucide?.createIcons(); }

// 图片压缩
async function compressImage(dataUrl, maxKB = 500) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      let w = img.width, h = img.height;
      const maxDim = 1200;
      if (w > maxDim || h > maxDim) {
        const ratio = Math.min(maxDim / w, maxDim / h);
        w = Math.round(w * ratio); h = Math.round(h * ratio);
      }
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, w, h);
      let quality = 0.85;
      let result = canvas.toDataURL("image/jpeg", quality);
      while (result.length > maxKB * 1024 && quality > 0.3) {
        quality -= 0.1;
        result = canvas.toDataURL("image/jpeg", quality);
      }
      resolve(result);
    };
    img.src = dataUrl;
  });
}

function fileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("图片读取失败，请重新选择"));
    reader.readAsDataURL(file);
  });
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图片无法识别，请选择 JPG、PNG 或 WebP 文件"));
    image.src = dataUrl;
  });
}

async function prepareAvatar(file) {
  const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
  if (!allowedTypes.includes(file.type)) throw new Error("仅支持 JPG、PNG 或 WebP 头像");
  if (file.size > 10 * 1024 * 1024) throw new Error("请选择小于 10MB 的头像图片");
  const image = await loadImage(await fileAsDataUrl(file));
  const size = 512;
  const crop = Math.min(image.width, image.height);
  const sourceX = (image.width - crop) / 2;
  const sourceY = (image.height - crop) / 2;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  canvas.getContext("2d").drawImage(image, sourceX, sourceY, crop, crop, 0, 0, size, size);
  return canvas.toDataURL("image/jpeg", 0.88);
}

async function prepareHandImage(file) {
  const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
  if (!allowedTypes.includes(file.type)) throw new Error("仅支持 JPG、PNG 或 WebP 手部图片");
  if (file.size > 10 * 1024 * 1024) throw new Error("请选择小于 10MB 的手部图片");
  const dataUrl = await fileAsDataUrl(file);
  await loadImage(dataUrl);
  return compressImage(dataUrl, 900);
}

// 分享功能
async function shareContent(type, item, score = null) {
  if (navigator.share) {
    try {
      const title = type === "style" ? `Bloom 推荐：${item.title}` : "我的 Bloom 美甲搭配方案";
      const text = score ? `【${item.title}】与我的匹配度 ${score}%！来看看适不适合你~` : `在 Bloom 发现了一款超美的【${item.title}】，来试试适不适合你！`;
      await navigator.share({ title, text, url: window.location.href });
      await api("/api/share", { method: "POST", body: JSON.stringify({ user_id: state.user?.id, target_type: type, target_id: item.id, platform: "web_share" }) }).catch(() => {});
    } catch {}
  } else {
    await navigator.clipboard.writeText(`Bloom 推荐：【${item.title}】${score ? `匹配度 ${score}%！` : ""}来试试吧！${window.location.href}`);
    toast("链接已复制，去分享给好友吧");
  }
}

async function shareTryonResult(style) {
  const canvas = document.querySelector("#tryon-canvas");
  if (!canvas || !tryonRuntime.hasFrame) return toast("请先打开摄像头或上传手部图片");
  const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
  if (!blob) return toast("试戴图片生成失败，请稍后重试");
  const file = new File([blob], `Bloom-${style.title || "虚拟试戴"}.png`, { type: "image/png" });
  const shareData = {
    title: `Bloom 虚拟试戴：${style.title}`,
    text: `我在 Bloom 试戴了【${style.title}】，看看效果怎么样？`,
    files: [file],
  };
  try {
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      await navigator.share(shareData);
      await api("/api/share", { method: "POST", body: JSON.stringify({ user_id: state.user?.id, target_type: "tryon", target_id: style.id, platform: "web_share" }) }).catch(() => {});
      return;
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = file.name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("试戴图已保存，可以发送给好友了");
  } catch (error) {
    if (error?.name !== "AbortError") toast("分享失败，请稍后重试");
  }
}

// 生成分享海报
async function generateSharePoster(style, score) {
  const canvas = document.createElement("canvas");
  canvas.width = 600; canvas.height = 800;
  const ctx = canvas.getContext("2d");
  // 背景渐变
  const bg = ctx.createLinearGradient(0, 0, 600, 800);
  bg.addColorStop(0, "#fff3f0"); bg.addColorStop(1, "#fffaf8");
  ctx.fillStyle = bg; ctx.fillRect(0, 0, 600, 800);
  // 品牌
  try {
    const logo = await loadImage("./assets/bloom-logo.webp");
    ctx.drawImage(logo, 252, 12, 96, 96);
  } catch {
    ctx.fillStyle = "#8c4745"; ctx.font = "bold 36px 'DM Sans'";
    ctx.textAlign = "center"; ctx.fillText("Bloom", 300, 76);
  }
  // 款式图
  if (style.image_url) {
    try {
      const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = style.image_url; });
      ctx.drawImage(img, 150, 120, 300, 300);
    } catch {}
  }
  // 款式名
  ctx.fillStyle = "#2b1f28"; ctx.font = "bold 28px 'Noto Sans SC'";
  ctx.fillText(style.title, 300, 470);
  // 标签
  ctx.fillStyle = "#715f66"; ctx.font = "16px 'Noto Sans SC'";
  ctx.fillText(style.tags?.join(" · ") || "", 300, 505);
  // 评分
  if (score) {
    ctx.fillStyle = "#8c4745"; ctx.font = "bold 48px 'DM Sans'";
    ctx.fillText(`${score}%`, 300, 570);
    ctx.fillStyle = "#715f66"; ctx.font = "16px 'Noto Sans SC'";
    ctx.fillText("综合匹配度", 300, 600);
  }
  // 底部
  ctx.fillStyle = "#a9605a"; ctx.font = "14px 'Noto Sans SC'";
  ctx.fillText("扫码进入 Bloom，找到最适合你的那一款", 300, 680);
  // 二维码占位
  ctx.strokeStyle = "#d7aaa5"; ctx.lineWidth = 2;
  ctx.strokeRect(230, 700, 140, 60);
  ctx.fillStyle = "#a9605a"; ctx.font = "12px 'Noto Sans SC'";
  ctx.fillText("扫码访问", 300, 735);
  return canvas.toDataURL("image/png");
}

function startThree() {
  const mount = document.querySelector("#three-bg");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.1, 100);
  camera.position.z = 8;
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight); mount.append(renderer.domElement);

  const mainGroup = new THREE.Group(); scene.add(mainGroup);

  // 主装饰环 - 美甲灵感
  const geo = new THREE.TorusKnotGeometry(1.2, .18, 120, 18);
  const mat = new THREE.MeshBasicMaterial({ color: 0xe7a2bc, wireframe: true, transparent: true, opacity: .18 });
  const knot = new THREE.Mesh(geo, mat); mainGroup.add(knot);

  // 外层旋转环
  const ringGeo = new THREE.TorusGeometry(2.0, .06, 32, 100);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0xf3c4d5, wireframe: true, transparent: true, opacity: .1 });
  const ring = new THREE.Mesh(ringGeo, ringMat); ring.rotation.x = Math.PI * .35; mainGroup.add(ring);

  // 第二个环
  const ring2Geo = new THREE.TorusGeometry(1.7, .04, 32, 80);
  const ring2Mat = new THREE.MeshBasicMaterial({ color: 0xc65e87, wireframe: true, transparent: true, opacity: .08 });
  const ring2 = new THREE.Mesh(ring2Geo, ring2Mat); ring2.rotation.x = Math.PI * .55; ring2.rotation.y = Math.PI * .25; mainGroup.add(ring2);

  // 美甲元素粒子 - 模拟闪钻
  const particlesGroup = new THREE.Group();
  const colors = [0xf9c8d8, 0xc65e87, 0xf3c4d5, 0xe9789f, 0xfff0f5, 0xb84872];
  for (let i = 0; i < 30; i++) {
    const size = .025 + Math.random() * .06;
    const g = i % 5 === 0
      ? new THREE.OctahedronGeometry(size, 0)  // 钻石形状
      : new THREE.SphereGeometry(size, 8, 8);
    const m = new THREE.MeshBasicMaterial({
      color: colors[Math.floor(Math.random() * colors.length)],
      transparent: true,
      opacity: .25 + Math.random() * .35,
    });
    const particle = new THREE.Mesh(g, m);
    particle.position.set(
      (Math.random() - .5) * 9,
      (Math.random() - .5) * 6,
      (Math.random() - .5) * 3
    );
    particle.userData = {
      speed: .002 + Math.random() * .006,
      amplitude: .3 + Math.random() * .8,
      offset: Math.random() * Math.PI * 2,
    };
    particlesGroup.add(particle);
  }
  mainGroup.add(particlesGroup);

  // 动画循环
  const tick = () => {
    knot.rotation.x += .0008;
    knot.rotation.y += .0012;
    mainGroup.rotation.z += .00015;
    ring.rotation.z -= .0004;
    ring2.rotation.z += .0006;
    ring2.rotation.x += .0003;

    // 粒子浮动
    particlesGroup.children.forEach(p => {
      p.position.y += Math.sin(Date.now() * .001 * p.userData.speed + p.userData.offset) * .003;
      p.rotation.x += .01;
      p.rotation.y += .015;
    });

    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  };
  tick();

  addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
}

async function loadData() {
  const [styles, posts, stores] = await Promise.all([
    api("/api/styles").catch(() => ({ styles: [] })),
    api("/api/community/posts").catch(() => ({ posts: [] })),
    api("/api/stores").catch(() => ({ stores: [] })),
  ]);
  state.styles = styles.styles; state.posts = posts.posts; state.stores = stores.stores || [];
  if (state.user) {
    try {
      const favs = await api(`/api/users/${state.user.id}/favorites`);
      state.favorites = favs.styles.map(x => x.id);
    } catch {}
    if (state.user.profile) state.profile = { ...state.profile, ...state.user.profile };
    state.tutorialRecommendations = rankStyles(state.profile);
  }
}

function shell(content) {
  const navs = [["home","首页","house"],["adapt","智能适配","sparkles"],["community","美甲社区","users"],["tryon","虚拟试戴","scan-face"],["stores","预约门店","map-pin"],["me","我的","user-round"]];
  app.innerHTML = `<div class="shell">
    <header class="topbar">
      <div class="brand"><img class="brand-logo" src="./assets/bloom-logo.webp" alt="Bloom Nail Studio" width="92" height="92"></div>
      <nav class="nav">${navs.map(([id,label,ic])=>`<button class="${state.activeView===id?"active":""}" data-view="${id}">${icon(ic,15)}${label}</button>`).join("")}</nav>
      <div class="search-box" id="search-box">
        <input type="text" id="search-input" placeholder="搜索美甲特征、颜色、风格..." autocomplete="off">
        <button class="search-btn" id="search-btn">${icon("search",16)}</button>
        <div class="search-dropdown" id="search-dropdown" style="display:none"></div>
      </div>
      <div class="actions">${state.user?`<button class="avatar-btn" data-view="me" title="我的">${avatarContent(state.user.name, state.user.avatar_url)}</button>`:`<button class="btn-secondary" data-open-auth>登录 / 注册</button>`}</div>
    </header>
    <main>${content}</main>
    <div class="mobile-nav">${navs.map(([id,label,ic])=>`<button class="${state.activeView===id?"active":""}" data-view="${id}">${icon(ic,17)}${label}</button>`).join("")}</div>
  </div>
  <div class="modal-backdrop" id="modal"><div class="modal" id="modal-content"></div></div>`;
  renderIcons();
}
function iconButton(name, label) { return `<button class="icon-btn" title="${label}" data-icon-action="${name}">${icon(name,17)}</button>`; }
async function navigate(view) {
  if (state.activeView === "tryon" && (view !== "tryon" || tryonRuntime.mode === "camera")) cleanupTryonView();
  state.activeView = view;
  await render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function styleCard(style) {
  const liked = state.favorites.includes(style.id);
  const imgSrc = style.image_url || `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="'+style.color_a+'"/><stop offset="100%" stop-color="'+style.color_b+'"/></linearGradient></defs><rect width="400" height="500" fill="url(#g)"/><text x="200" y="260" text-anchor="middle" fill="white" font-size="22" font-family="sans-serif" font-weight="bold">'+style.title+'</text></svg>')}`;
  return `<article class="style-card">
    <div class="style-image" style="--c1:${style.color_a};--c2:${style.color_b}"><img src="${imgSrc}" alt="${escapeHtml(style.title)}" onerror="this.style.display='none';this.parentElement.style.background='linear-gradient(145deg,'+this.parentElement.style.getPropertyValue('--c1')+','+this.parentElement.style.getPropertyValue('--c2')+')';"><span class="style-badge">${escapeHtml(style.category)}</span><button class="favorite${liked ? " is-favorited" : ""}" data-favorite="${style.id}" title="${liked ? "已收藏" : "收藏"}" aria-label="${liked ? "已收藏" : "收藏"}${escapeHtml(style.title)}" aria-pressed="${liked}">${icon("heart",15)}</button></div>
    <div class="style-body"><div class="style-title"><strong>${escapeHtml(style.title)}</strong><span class="price">¥${escapeHtml(style.price)}</span></div>
    <div class="meta">${style.tags.slice(0,2).map(x=>`<span>${escapeHtml(x)}</span>`).join("")}<span>${escapeHtml(style.scene)}</span></div>
    <div class="card-actions"><button class="btn-secondary" data-tryon="${style.id}">${icon("scan-face",14)}试戴</button><button class="btn-primary" data-book="${style.id}">${icon("calendar-days",14)}预约</button></div>
    <button class="btn-douyin" data-douyin="${style.id}">🎵 在抖音查看同款</button></div>
  </article>`;
}

const tutorialOptions = {
  tutorial_hand_type: [
    { label: "肉肉手", detail: "指腹圆润，适合留出轻盈感", profileValue: "圆润型", icon: "hand", image: "assets/onboarding/hand-meaty.webp" },
    { label: "短粗手", detail: "甲型向前延伸，更显手长", profileValue: "短指型", icon: "move-up-right", image: "assets/onboarding/hand-short.webp" },
    { label: "骨节手", detail: "线条清晰，适合利落轮廓", profileValue: "骨感型", icon: "scan-line", image: "assets/onboarding/hand-jointed.webp" },
    { label: "修长手", detail: "比例舒展，款式适配度高", profileValue: "纤长型", icon: "ruler", image: "assets/onboarding/hand-slender.webp" },
    { label: "圆锥手", detail: "指尖收拢，适合优雅弧线", profileValue: "纤长型", icon: "triangle", image: "assets/onboarding/hand-conical.webp" },
    { label: "匀称手", detail: "线条平衡，可按场景大胆挑选", profileValue: "纤长型", icon: "sparkles", image: "assets/onboarding/hand-balanced.webp" },
  ],
  tutorial_nail_shape: [
    { label: "梯形", detail: "边缘微收，视觉更利落", profileValue: "方甲", icon: "square", image: "assets/onboarding/nail-trapezoid.jpg" },
    { label: "尖型", detail: "拉长指尖，适合精致氛围", profileValue: "杏仁甲", icon: "move-up", image: "assets/onboarding/nail-pointed.jpg" },
    { label: "圆形", detail: "自然柔和，短甲也轻松", profileValue: "圆甲", icon: "circle", image: "assets/onboarding/nail-round.jpg" },
    { label: "椭圆形", detail: "柔化线条，日常不挑手", profileValue: "杏仁甲", icon: "ellipse", image: "assets/onboarding/nail-oval.jpg" },
    { label: "方形", detail: "干净有力量，适合简约款", profileValue: "方甲", icon: "square-stack", image: "assets/onboarding/nail-square.jpg" },
    { label: "方圆形", detail: "方中带圆，耐看又百搭", profileValue: "方圆甲", icon: "app-window", image: "assets/onboarding/nail-squoval.jpg" },
  ],
  skin_tone: [
    { label: "冷白皮", detail: "清冷通透，适合低饱和与冷色光泽", profileValue: "冷白皮", tone: "#f7d5cf", image: "assets/onboarding/skin-cool-light.jpg" },
    { label: "黄白皮", detail: "偏暖明亮，奶杏与玫瑰色更显白", profileValue: "暖黄皮", tone: "#eab58c", image: "assets/onboarding/skin-warm-light.jpg" },
    { label: "自然黄皮", detail: "自然健康，红棕、豆沙与暖裸色友好", profileValue: "自然肤色", tone: "#c98962", image: "assets/onboarding/skin-natural.jpg" },
    { label: "深肤色", detail: "深邃有质感，高对比与珠光更出彩", profileValue: "小麦色", tone: "#84513c", image: "assets/onboarding/skin-deep.jpg" },
  ],
  scene: [
    { label: "日常", detail: "耐看、好搭配", icon: "coffee", image: "assets/community/cn_cream_1.webp" },
    { label: "通勤", detail: "克制、有质感", icon: "briefcase-business", image: "assets/community/cn_short_work_1.webp" },
    { label: "约会", detail: "精致、有氛围", icon: "heart", image: "assets/community/cn_blush_french_1.webp" },
    { label: "婚礼", detail: "柔和、有仪式感", icon: "gem", image: "assets/community/cn_bride_1.webp" },
    { label: "聚会", detail: "吸睛、有光泽", icon: "party-popper", image: "assets/community/cn_cat_eye_1.webp" },
    { label: "节日", detail: "鲜明、有记忆点", icon: "calendar-heart", image: "assets/community/cn_dopamine_1.webp" },
  ],
  color_preference: [
    { label: "清透浅色", detail: "果冻、奶白与低饱和粉", tone: "#f7d9e4", image: "assets/community/cn_glass_1.webp" },
    { label: "显白暖色", detail: "红棕、莓果与暖调玫瑰", tone: "#b74c62", image: "assets/community/cn_red_brown_1.webp" },
    { label: "低饱和裸色", detail: "奶茶、灰粉与自然裸调", tone: "#bea091", image: "assets/community/cn_cream_2.webp" },
    { label: "冷感光泽", detail: "冰透、猫眼与极光光影", tone: "#a7b8d8", image: "assets/community/cn_cat_eye_2.webp" },
  ],
  style_preference: [
    { label: "基础纯色", detail: "纯色、跳色与腮红甲", icon: "palette", image: "assets/onboarding/style-basic.jpg" },
    { label: "法式", detail: "标准、高位、V 法式与微法式", icon: "smile-plus", image: "assets/onboarding/style-french.jpg" },
    { label: "渐变晕染", detail: "渐变、水墨、醋酸与大理石", icon: "waves", image: "assets/onboarding/style-gradient.jpg" },
    { label: "特殊质感", detail: "猫眼、碎钻、极光与磨砂", icon: "sparkle", image: "assets/onboarding/style-texture.jpg" },
    { label: "手绘纹理", detail: "手绘、大理石与浮雕雕花", icon: "brush", image: "assets/onboarding/style-handpainted.jpg" },
    { label: "饰品装饰", detail: "钻饰、珍珠、金属与 3D 饰品", icon: "gem", image: "assets/onboarding/style-decoration.jpg" },
  ],
  decoration_preference: [
    { label: "不加饰品", detail: "让色彩与甲型成为主角", image: "assets/community/cn_minimal_1.webp" },
    { label: "细闪薄片", detail: "轻量提亮，不抢主色", image: "assets/onboarding/style-decoration.jpg" },
    { label: "珍珠金属", detail: "增加细节与精致感", image: "assets/onboarding/decoration-jewelry.jpg" },
    { label: "钻饰", detail: "适合局部点缀与仪式场景", image: "assets/onboarding/decoration-jewelry.jpg" },
    { label: "3D 饰品", detail: "立体吸睛，适合重点手指", image: "assets/onboarding/decoration-stickers.jpg" },
  ],
};

const tutorialStyleMatches = {
  "基础纯色": ["纯色", "裸色", "甜美", "果冻"],
  "法式": ["法式"],
  "渐变晕染": ["渐变", "晕染", "大理石"],
  "特殊质感": ["猫眼", "镜面", "极光", "磨砂"],
  "手绘纹理": ["花卉", "大理石", "手绘"],
  "饰品装饰": ["闪钻", "珍珠", "3D", "甜美"],
};

function rankStyles(profile = state.profile) {
  const preferredTerms = tutorialStyleMatches[profile.style_preference || profile.style] || [];
  return [...state.styles].map(style => {
    const terms = [style.category, ...(style.tags || [])];
    let score = 0;
    if ((style.skin_tones || []).includes(profile.skin_tone)) score += 4;
    if ((style.nail_shapes || []).includes(profile.nail_shape)) score += 4;
    if (style.scene === profile.scene) score += 3;
    if (preferredTerms.some(term => terms.some(value => value.includes(term)))) score += 3;
    if (["纤长型", "骨感型"].includes(profile.hand_shape) && ["法式", "渐变", "轻奢", "闪钻", "猫眼", "镜面"].includes(style.category)) score += 1;
    if (["圆润型", "短指型"].includes(profile.hand_shape) && ["纯色", "裸色", "甜美", "法式"].includes(style.category)) score += 1;
    return { ...style, tutorial_score: score };
  }).sort((a, b) => b.tutorial_score - a.tutorial_score || (b.likes || 0) - (a.likes || 0));
}

function tutorialDraftFromProfile() {
  const profile = state.user?.profile || {};
  const selected = (key, fallbackIndex = 0) => {
    const options = tutorialOptions[key];
    const direct = options.find(option => option.label === profile[key]);
    if (direct) return direct.label;
    const mapped = options.find(option => option.profileValue && option.profileValue === profile[key]);
    return (mapped || options[fallbackIndex]).label;
  };
  return {
    tutorial_hand_type: selected("tutorial_hand_type"),
    tutorial_nail_shape: selected("tutorial_nail_shape", 5),
    skin_tone: selected("skin_tone", 2),
    scene: selected("scene"),
    color_preference: selected("color_preference"),
    style_preference: selected("style_preference"),
    decoration_preference: selected("decoration_preference"),
  };
}

function selectedTutorialOption(field, label) {
  return tutorialOptions[field].find(option => option.label === label) || tutorialOptions[field][0];
}

function tutorialChoices(field, draft) {
  return tutorialOptions[field].map((option, index) => {
    const selected = draft[field] === option.label;
    const badge = option.tone ? `<span class="tutorial-choice-badge tutorial-swatch" style="--tutorial-tone:${option.tone}"></span>` : option.icon ? `<span class="tutorial-choice-badge">${icon(option.icon, 16)}</span>` : "";
    const image = option.image ? `<img src="${escapeHtml(option.image)}" alt="${escapeHtml(option.label)}示例图" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false">` : "";
    const placeholder = `<span class="tutorial-media-placeholder" ${option.image ? "hidden" : ""}>${icon("image-off", 21)}<small>素材准备中</small></span>`;
    return `<button class="tutorial-choice ${selected ? "selected" : ""}" type="button" data-tutorial-field="${field}" data-tutorial-index="${index}" aria-pressed="${selected}"><span class="tutorial-choice-media">${image}${placeholder}${badge}</span><span class="tutorial-choice-info"><strong>${escapeHtml(option.label)}</strong><small>${escapeHtml(option.detail)}</small></span></button>`;
  }).join("");
}

function tutorialRecommendationCard(style) {
  const image = style.image_url || "";
  return `<article class="tutorial-recommendation"><img src="${escapeHtml(image)}" alt="${escapeHtml(style.title)}"><div><strong>${escapeHtml(style.title)}</strong><small>${escapeHtml(style.category)} · ${escapeHtml(style.scene)}</small></div></article>`;
}

function syncUserProfile(user) {
  state.user = user;
  state.profile = { ...state.profile, ...(user.profile || {}) };
  state.recommendationPlan = user.profile?.latest_recommendation_plan || state.recommendationPlan;
  state.tutorialRecommendations = rankStyles(state.profile);
  localStorage.setItem("md_user", JSON.stringify(state.user));
}

function openOnboarding({ restart = false } = {}) {
  if (!state.user) return openAuth();
  const modal = document.querySelector("#modal");
  const box = document.querySelector("#modal-content");
  if (!modal || !box) return;
  const draft = tutorialDraftFromProfile();
  let stage = restart ? 1 : 0;

  const saveProfile = async (patch) => {
    const result = await api("/api/profile", { method: "POST", body: JSON.stringify({ profile: patch }) });
    syncUserProfile(result.user);
  };

  const renderTutorial = () => {
    modal.classList.add("open");
    if (stage === 0) {
      box.innerHTML = `<div class="tutorial-welcome"><span class="tutorial-welcome-mark">${icon("sparkles", 24)}</span><p class="tutorial-kicker">YOUR NAIL EDIT</p><h3>从了解自己的手开始</h3><p>用不到两分钟，找到适合你的甲型、色彩与款式方向。</p><div class="tutorial-welcome-notes"><span>${icon("hand", 15)}手型与甲型</span><span>${icon("palette", 15)}肤色与色彩</span><span>${icon("gem", 15)}风格与饰品</span></div><div class="tutorial-actions"><button class="btn-secondary" id="onboarding-skip" type="button">暂时跳过</button><button class="btn-primary" id="onboarding-start" type="button">开始教程 ${icon("arrow-right", 15)}</button></div></div>`;
      renderIcons();
      document.querySelector("#onboarding-start").addEventListener("click", () => { stage = 1; renderTutorial(); });
      document.querySelector("#onboarding-skip").addEventListener("click", async () => {
        try {
          await saveProfile({ onboarding_status: "skipped" });
          closeModal();
          toast("已跳过教程，可随时在“我的”页面重新开始");
        } catch (error) {
          toast(error.message || "保存教程状态失败，请稍后重试");
        }
      });
      return;
    }

    const steps = [
      { field: "tutorial_hand_type", title: "先看看你的手型", copy: "了解手部线条，挑选甲型时就更有方向。" },
      { field: "tutorial_nail_shape", title: "选择想尝试的甲型", copy: "不同轮廓会修饰指尖比例，也影响整体风格。" },
      { field: "skin_tone", title: "找到更衬肤色的方向", copy: "不是限制，而是帮你更快找到显白、有质感的色彩。" },
      { field: "scene", title: "你最常为哪个场景做美甲？", copy: "让好看也能自然融入你的日常。" },
    ];

    if (stage <= 4) {
      const current = steps[stage - 1];
      box.innerHTML = `<div class="tutorial-head"><div><span class="tutorial-kicker">第 ${stage} / 5 步</span><h3>${current.title}</h3></div>${restart ? `<button class="close" id="close-tutorial" title="关闭教程">${icon("x", 17)}</button>` : ""}</div><p class="tutorial-copy">${current.copy}</p><div class="tutorial-progress" aria-label="教程进度"><span style="width:${stage / 5 * 100}%"></span></div><div class="tutorial-choice-grid tutorial-grid-${current.field}">${tutorialChoices(current.field, draft)}</div><div class="tutorial-actions tutorial-step-actions">${stage > 1 ? `<button class="btn-secondary" id="onboarding-back" type="button">${icon("arrow-left", 15)}上一步</button>` : `<span></span>`}<button class="btn-primary" id="onboarding-next" type="button">下一步 ${icon("arrow-right", 15)}</button></div>`;
      document.querySelectorAll("[data-tutorial-field]").forEach(button => button.addEventListener("click", () => {
        const field = button.dataset.tutorialField;
        draft[field] = tutorialOptions[field][Number(button.dataset.tutorialIndex)].label;
        renderTutorial();
      }));
      document.querySelector("#onboarding-back")?.addEventListener("click", () => { stage -= 1; renderTutorial(); });
      document.querySelector("#onboarding-next").addEventListener("click", () => { stage += 1; renderTutorial(); });
      document.querySelector("#close-tutorial")?.addEventListener("click", closeModal);
      renderIcons();
      return;
    }

    if (stage === 5) {
      box.innerHTML = `<div class="tutorial-head"><div><span class="tutorial-kicker">第 5 / 5 步</span><h3>定下你的风格方向</h3></div>${restart ? `<button class="close" id="close-tutorial" title="关闭教程">${icon("x", 17)}</button>` : ""}</div><p class="tutorial-copy">色彩由主色、色胶与装饰层次共同决定；先选你想表达的感觉，再决定点缀程度。</p><div class="tutorial-progress" aria-label="教程进度"><span style="width:100%"></span></div><div class="tutorial-preference-group"><h4>偏好色彩</h4><div class="tutorial-choice-grid compact">${tutorialChoices("color_preference", draft)}</div></div><div class="tutorial-preference-group"><h4>款式方向</h4><div class="tutorial-choice-grid compact">${tutorialChoices("style_preference", draft)}</div></div><div class="tutorial-preference-group"><h4>饰品程度</h4><div class="tutorial-choice-grid compact">${tutorialChoices("decoration_preference", draft)}</div></div><div class="tutorial-actions tutorial-step-actions"><button class="btn-secondary" id="onboarding-back" type="button">${icon("arrow-left", 15)}上一步</button><button class="btn-primary" id="onboarding-next" type="button">查看我的档案 ${icon("arrow-right", 15)}</button></div>`;
      document.querySelectorAll("[data-tutorial-field]").forEach(button => button.addEventListener("click", () => {
        const field = button.dataset.tutorialField;
        draft[field] = tutorialOptions[field][Number(button.dataset.tutorialIndex)].label;
        renderTutorial();
      }));
      document.querySelector("#onboarding-back").addEventListener("click", () => { stage = 4; renderTutorial(); });
      document.querySelector("#onboarding-next").addEventListener("click", () => { stage = 6; renderTutorial(); });
      document.querySelector("#close-tutorial")?.addEventListener("click", closeModal);
      renderIcons();
      return;
    }

    const hand = selectedTutorialOption("tutorial_hand_type", draft.tutorial_hand_type);
    const nail = selectedTutorialOption("tutorial_nail_shape", draft.tutorial_nail_shape);
    const skin = selectedTutorialOption("skin_tone", draft.skin_tone);
    const recommendations = rankStyles({
      ...draft,
      hand_shape: hand.profileValue,
      nail_shape: nail.profileValue,
      skin_tone: skin.profileValue,
    }).slice(0, 3);
    box.innerHTML = `<div class="tutorial-head"><div><span class="tutorial-kicker">你的挑选笔记</span><h3>适合你的方向已经清晰</h3></div>${restart ? `<button class="close" id="close-tutorial" title="关闭教程">${icon("x", 17)}</button>` : ""}</div><p class="tutorial-copy">先从 ${escapeHtml(draft.style_preference)} 和 ${escapeHtml(draft.color_preference)} 开始，${escapeHtml(nail.label)} 会更贴合你选择的手部线条。</p><div class="tutorial-summary"><span>${icon("hand", 15)}${escapeHtml(draft.tutorial_hand_type)}</span><span>${icon("app-window", 15)}${escapeHtml(draft.tutorial_nail_shape)}</span><span>${icon("palette", 15)}${escapeHtml(draft.skin_tone)}</span><span>${icon("briefcase-business", 15)}${escapeHtml(draft.scene)}</span></div><div class="tutorial-result-note"><strong>挑选建议</strong><p>${escapeHtml(hand.detail)} ${escapeHtml(skin.detail)}</p></div><div class="tutorial-recommendations">${recommendations.map(tutorialRecommendationCard).join("")}</div><div class="tutorial-actions tutorial-step-actions"><button class="btn-secondary" id="onboarding-back" type="button">${icon("arrow-left", 15)}返回修改</button><button class="btn-primary" id="onboarding-finish" type="button">建立档案并适配 ${icon("sparkles", 15)}</button></div>`;
    document.querySelector("#onboarding-back").addEventListener("click", () => { stage = 5; renderTutorial(); });
    document.querySelector("#onboarding-finish").addEventListener("click", async (event) => {
      try {
        event.currentTarget.disabled = true;
        await saveProfile({
          ...draft,
          hand_shape: hand.profileValue,
          nail_shape: nail.profileValue,
          skin_tone: skin.profileValue,
          style: draft.style_preference,
          onboarding_status: "completed",
        });
        closeModal();
        state.activeView = "adapt";
        await render();
        toast("搭配档案已建立，已为你更新推荐款式");
      } catch (error) {
        event.currentTarget.disabled = false;
        toast(error.message || "保存搭配档案失败，请稍后重试");
      }
    });
    document.querySelector("#close-tutorial")?.addEventListener("click", closeModal);
    renderIcons();
  };

  renderTutorial();
}

function bindStyleActions() {
  document.querySelectorAll("[data-favorite]").forEach(btn => btn.addEventListener("click", async () => {
    if (!state.user) return openAuth();
    const styleId = Number(btn.dataset.favorite);
    const isFavorited = state.favorites.includes(styleId);
    try {
      btn.disabled = true;
      if (isFavorited) {
        await api("/api/favorites", { method:"DELETE", body:JSON.stringify({ style_id: styleId }) });
        state.favorites = state.favorites.filter(id => id !== styleId);
        toast("已取消收藏");
      } else {
        await api("/api/favorites", { method:"POST", body:JSON.stringify({ user_id: state.user.id, style_id: styleId }) });
        state.favorites.push(styleId);
        toast("已收藏到你的灵感夹");
      }
      await render();
    } catch (error) {
      toast(error.message || (isFavorited ? "取消收藏失败，请稍后重试" : "收藏失败，请稍后重试"));
    } finally {
      btn.disabled = false;
    }
  }));
  document.querySelectorAll("[data-tryon]").forEach(btn => btn.addEventListener("click", () => { state.selectedStyle = state.styles.find(x => x.id === Number(btn.dataset.tryon)); navigate("tryon"); }));
  document.querySelectorAll("[data-book]").forEach(btn => btn.addEventListener("click", () => { state.selectedStyle = state.styles.find(x => x.id === Number(btn.dataset.book)); openBooking(); }));
  // 抖音查看同款
  document.querySelectorAll("[data-douyin]").forEach(btn => btn.addEventListener("click", () => {
    const style = state.styles.find(x => x.id === Number(btn.dataset.douyin));
    if (style) {
      const kw = encodeURIComponent(`${style.title} ${style.category} ${(style.tags||[]).slice(0,3).join(" ")} 美甲`);
      window.open(`https://www.douyin.com/search/${kw}?type=general`, "_blank");
      toast(`正在抖音搜索「${style.title}」同款`);
    }
  }));
}

function homeView() {
  const featured = state.styles.slice(0,4);
  return `<section class="hero"><div class="hero-copy"><span class="eyebrow">${icon("sparkles",14)}你的专属美甲搭配空间</span><h1>先了解你的手，<br><span>再决定这一款。</span></h1><p>上传一张手部照片，或者打开摄像头，让 Bloom 根据肤色、手型、甲型和生活场景，为你找到更适合的美甲灵感。</p><div class="hero-actions"><button class="btn-primary" data-view="adapt">${icon("scan-face",16)}开始智能适配</button><button class="btn-secondary" data-view="community">${icon("compass",16)}逛逛美甲社区</button></div><div class="hero-note">${icon("shield-check",15)}<span>你的照片仅用于本次体验，<b>不会公开发布</b></span></div></div><div class="hero-visual"><img class="hero-visual-image" src="./assets/home-inspiration.webp" alt="莓果粉轻法式美甲双手展示" width="830" height="928" loading="eager" fetchpriority="high" decoding="async"><div class="hero-visual-copy"><small>本周灵感主题</small><strong>莓果粉 · 轻法式</strong></div></div></section>
  <section class="section"><div class="section-head"><div><h2>为你挑的款式</h2><p>先从高匹配、好上手的日常风格开始</p></div><button class="btn-ghost" data-view="community">查看全部 ${icon("arrow-right",15)}</button></div><div class="grid">${featured.map(styleCard).join("")}</div></section>
  <section class="section"><div class="section-head"><div><h2>社区正在发生</h2><p>看看大家真实上手的美甲</p></div><button class="btn-ghost" data-view="community">去社区 ${icon("arrow-right",15)}</button></div><div class="community-grid">${state.posts.slice(0,3).map(postCard).join("") || `<div class="empty">社区还在准备第一批灵感</div>`}</div></section>`;
}
function filteredCommunityPosts(filter = state.communityFilter) {
  if (filter === "全部") return state.posts;
  return state.posts.filter(post => post.category === filter || (post.tags || []).includes(filter));
}

function filteredCommunityStyles(filter = state.communityFilter) {
  if (filter === "全部" || filter === "探店") return state.styles;
  const aliases = {
    "新中式": ["花卉","晕染","复古","大理石","琥珀"],
    "新娘": ["闪钻","3D立体","蕾丝","花卉"],
    "短甲友好": ["极简","法式","果冻"],
    "显白": ["猫眼","渐变","复古"]
  };
  return state.styles.filter(style => {
    const tags = style.tags || [];
    const shapes = style.nail_shapes || [];
    if (style.category === filter || tags.includes(filter)) return true;
    if (filter === "短甲友好" && shapes.includes("短甲")) return true;
    if (filter === "新娘" && style.scene === "婚礼") return true;
    return (aliases[filter] || []).includes(style.category);
  });
}

function postCard(post) {
  const tags = (post.tags || []).slice(0, 3);
  const sourceUrl = /^https?:\/\//.test(post.source_url || "") ? escapeHtml(post.source_url) : "";
  const source = sourceUrl ? `<a class="post-source" href="${sourceUrl}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(post.source_license || "图片来源")}">${icon("image", 11)} 查看来源</a>` : "";
  return `<article class="post-card ${post.featured ? "featured" : ""}">
    <div class="post-media"><img src="${escapeHtml(post.image_data)}" alt="${escapeHtml(post.title)}" loading="lazy"><div class="post-media-top"><span class="post-category">${escapeHtml(post.category || "灵感")}</span>${post.editorial ? `<span class="editorial-badge">编辑精选</span>` : ""}</div></div>
    <div class="post-body"><div class="post-author"><span class="post-avatar">${avatarContent(post.user_name || "美", post.user_avatar_url)}</span><div><strong>${escapeHtml(post.user_name || "搭配师用户")}</strong><small>${post.editorial ? "社区灵感采编" : "真实用户分享"}</small></div>${source}</div>
    <h3>${escapeHtml(post.title)}</h3><p>${escapeHtml(post.body || "分享我的近期美甲灵感。")}</p>
    ${tags.length ? `<div class="post-tags">${tags.map(tag => `<span>#${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
    <div class="post-meta"><span>${icon("sparkles", 12)} ${escapeHtml(post.category || "美甲灵感")}</span><div class="post-actions"><button class="post-action-btn" data-like-post="${post.id}" title="点赞">${icon("heart",13)} <span>${post.likes || 0}</span></button><button class="post-action-btn" data-comment-post="${post.id}" title="评论">${icon("message-circle",13)} <span>${post.comment_count || 0}</span></button></div></div></div></article>`;
}

function adaptView() {
  const recommendations = (state.tutorialRecommendations.length ? state.tutorialRecommendations : rankStyles(state.profile)).slice(0, 4);
  const selected = value => `value="${value}" ${state.profile.skin_tone === value ? "selected" : ""}`;
  const selectedHand = value => `value="${value}" ${state.profile.hand_shape === value ? "selected" : ""}`;
  const selectedNail = value => `value="${value}" ${state.profile.nail_shape === value ? "selected" : ""}`;
  const selectedScene = value => `value="${value}" ${state.profile.scene === value ? "selected" : ""}`;
  return `<section class="section"><div class="section-head"><div><h2>智能适配</h2><p>填写几个轻量信息，系统就能给你一份更懂你的搭配建议</p></div></div><div class="adapt-layout"><div class="panel"><h3>建立你的手部档案</h3><p class="lead">可以上传本地照片，也可以使用摄像头。照片只用于当前体验。</p><div class="upload-box"><div>${icon("upload",30)}</div><strong>上传手部照片</strong><small>支持 JPG、PNG，建议使用自然光、手背朝上照片</small><input id="hand-upload" type="file" accept="image/*" style="display:none"><div style="margin-top:13px;display:flex;gap:8px;justify-content:center"><button class="btn-primary" id="choose-hand">${icon("folder-open",14)}打开本地文件</button><button class="btn-secondary" id="camera-hand">${icon("camera",14)}打开摄像头</button></div></div><div id="camera-box" style="display:none;margin-top:12px"><video id="camera-video" autoplay playsinline style="width:100%;border-radius:12px;background:#2b1f28"></video><button class="btn-secondary" id="capture-hand" style="width:100%;margin-top:8px">${icon("aperture",14)}拍摄当前画面</button></div><div class="form-grid"><div class="field"><label>肤色</label><select id="skin-tone"><option ${selected("冷白皮")}>冷白皮</option><option ${selected("自然肤色")}>自然肤色</option><option ${selected("暖黄皮")}>暖黄皮</option><option ${selected("小麦色")}>小麦色</option></select></div><div class="field"><label>手型</label><select id="hand-shape"><option ${selectedHand("纤长型")}>纤长型</option><option ${selectedHand("圆润型")}>圆润型</option><option ${selectedHand("骨感型")}>骨感型</option><option ${selectedHand("短指型")}>短指型</option></select></div><div class="field"><label>甲型基础</label><select id="nail-shape"><option ${selectedNail("圆甲")}>圆甲</option><option ${selectedNail("方圆甲")}>方圆甲</option><option ${selectedNail("杏仁甲")}>杏仁甲</option><option ${selectedNail("方甲")}>方甲</option><option ${selectedNail("短甲")}>短甲</option><option ${selectedNail("长甲")}>长甲</option></select></div><div class="field"><label>常见场景</label><select id="scene"><option ${selectedScene("日常")}>日常</option><option ${selectedScene("通勤")}>通勤</option><option ${selectedScene("约会")}>约会</option><option ${selectedScene("婚礼")}>婚礼</option><option ${selectedScene("聚会")}>聚会</option><option ${selectedScene("节日")}>节日</option></select></div></div><button class="btn-primary" id="analyze-btn" style="width:100%;margin-top:16px">${icon("wand-sparkles",15)}生成我的适配档案</button><div class="analysis-result" id="analysis-result"></div></div><div class="panel"><h3>推荐款式</h3><p class="lead">${state.user?.profile?.onboarding_status === "completed" ? "已按你的新手档案排序，可继续查看匹配评分。" : "选择一款喜欢的作品，看看它与你的手部条件是否合拍。"}</p><div class="grid" id="adapt-results" style="grid-template-columns:repeat(2,minmax(0,1fr))">${recommendations.map(styleCard).join("")}</div></div></div></section>`;
}

function communityView() {
  const featured = state.posts.find(post => post.featured) || state.posts[0];
  const filters = ["全部","猫眼","新中式","短甲友好","法式","显白","极简","新娘","果冻","花卉","几何","探店"];
  const feed = filteredCommunityPosts();
  return `<section class="community-page">
    <div class="community-hero">${featured ? `<div class="community-cover"><img src="${escapeHtml(featured.image_data)}" alt="${escapeHtml(featured.title)}"><div class="community-cover-shade"></div><div class="community-cover-copy"><span>WEEKLY NAIL EDIT</span><h1>把喜欢的款式，<br>变成适合你的那一款。</h1><p>${escapeHtml(featured.body)}</p><button class="hero-community-btn" data-comment-post="${featured.id}">查看本期灵感 ${icon("arrow-up-right",15)}</button></div></div>` : ""}
      <aside class="community-intro-card"><span class="eyebrow">${icon("orbit",14)} 国内灵感雷达</span><h2>本周大家都在看</h2><div class="trend-list"><button data-community-filter="短甲友好"><b>01</b><span>短甲通勤<small>干净、显手长</small></span></button><button data-community-filter="猫眼"><b>02</b><span>冰透猫眼<small>玻璃珠流动光</small></span></button><button data-community-filter="新中式"><b>03</b><span>轻国风设计<small>玉石、青花与金属</small></span></button><button data-community-filter="显白"><b>04</b><span>红棕显白色<small>适合暖黄皮与秋冬</small></span></button></div><div class="community-numbers"><div><strong>${state.posts.length}</strong><span>篇灵感</span></div><div><strong>${state.styles.length}</strong><span>种款式</span></div><div><strong>${state.posts.reduce((sum,p)=>sum+(p.likes||0),0)}</strong><span>次心动</span></div></div></aside>
    </div>
    <div class="community-toolbar"><div><span class="eyebrow">COMMUNITY LOOKBOOK</span><h2>今天想做哪一种？</h2></div><button class="btn-primary" id="publish-post">${icon("plus",15)}发布我的美甲</button></div>
    <div class="community-filter-row">${filters.map(x=>`<button class="community-filter ${state.communityFilter===x?"active":""}" data-community-filter="${x}">${x}</button>`).join("")}</div>
    <div class="community-content"><main><div class="community-feed" id="community-feed">${feed.map(postCard).join("") || `<div class="empty community-empty">这个主题还没有内容，来发布第一篇吧。</div>`}</div></main><aside class="community-sidebar"><div class="sidebar-card"><span class="eyebrow">投稿指南</span><h3>让你的晒图更好看</h3><ul><li>用自然光，避免甲面强反光</li><li>标题写清甲型、颜色和元素</li><li>分享价格、保持时间与踩坑点</li></ul><button class="btn-secondary" id="sidebar-publish">开始分享</button></div><div class="sidebar-card soft"><span class="eyebrow">素材说明</span><p>编辑精选已替换为国内美甲客照与国内平台公开检索素材，并全部保存到本地，避免热链失效。当前用于产品原型展示，正式商用前需取得原作者授权；用户上传会标注为真实分享。</p></div></aside></div>
    <div class="community-style-section"><div class="section-head"><div><span class="eyebrow">MATCH THE LOOK</span><h2>从灵感直接找到同类款式</h2><p>图片已按国内流行款式重新整理：冰透猫眼、新中式、显白红棕、短甲通勤等，不再混入无关照片。</p></div></div><div class="grid community-style-grid" id="community-styles">${filteredCommunityStyles().slice(0,8).map(styleCard).join("")}</div></div>
  </section>`;
}

function tryonView() {
  const style = state.selectedStyle || state.styles[0];
  const matchInfo = state.matchResult;
  return `<section class="section tryon-page"><div class="section-head"><div><h2>虚拟试戴</h2><p>打开电脑前置摄像头实时跟随双手，或上传照片查看上手效果</p></div></div><div class="panel"><div class="tryon-wrap"><div class="tryon-preview"><div class="tryon-stage" id="tryon-stage"><canvas id="tryon-canvas" aria-label="Bloom 虚拟试戴预览"></canvas><video id="tryon-video" autoplay muted playsinline hidden></video><div class="tryon-empty" id="tryon-empty" ${state.handImage ? "hidden" : ""}>${icon("scan-face",32)}<div><strong>开始你的虚拟试戴</strong><span>手背朝向镜头、手指自然展开，识别会更准确</span></div></div><button class="tryon-close-camera" id="tryon-close-camera" type="button" title="关闭摄像头" aria-label="关闭摄像头" hidden>${icon("x",18)}</button><div class="tryon-status" id="tryon-status" role="status" aria-live="polite" data-tone="neutral">${state.handImage ? "正在识别图片中的手部" : "摄像头画面和图片仅在浏览器本地处理"}</div></div><div class="tryon-source-actions"><input id="tryon-file" type="file" accept="image/jpeg,image/png,image/webp" hidden><button class="btn-primary" id="tryon-camera" type="button">${icon("video",15)}打开前置摄像头</button><button class="btn-secondary" id="tryon-upload" type="button">${icon("image-plus",15)}${state.handImage ? "更换图片" : "上传图片"}</button></div><p class="tryon-privacy">${icon("shield-check",14)}画面在本机实时处理，不会上传或保存摄像头内容。</p></div><div><div class="score-card"><h4>当前试戴款式</h4><strong style="font-size:20px">${escapeHtml(style.title)}</strong><div class="meta">${style.tags.map(x=>`<span>${escapeHtml(x)}</span>`).join("")}</div><div class="tryon-controls"><div class="field"><label for="nail-color">颜色</label><input type="color" id="nail-color" value="${normalizeHexColor(style.color_a)}"></div><div class="field"><label for="tryon-shape">甲型</label><select id="tryon-shape"><option value="round">圆甲</option><option value="square" selected>方甲</option><option value="almond">杏仁甲</option><option value="stiletto">尖甲</option></select></div><div class="field"><label for="tryon-length">长度</label><input type="range" id="tryon-length" min="0.7" max="1.5" step="0.05" value="1"></div></div><p>虚拟预览用于辅助决策，实际效果会受甲面长度、光线和美甲师工艺影响。</p><button class="btn-primary" id="match-now" style="width:100%">${icon("sparkles",15)}查看匹配评分</button><button class="btn-secondary" id="book-from-tryon" style="width:100%;margin-top:9px">${icon("calendar-days",15)}预约这款</button><button class="btn-ghost" id="share-tryon" style="width:100%;margin-top:6px">${icon("share-2",14)}分享试戴效果</button></div><div id="match-result" style="margin-top:12px">${matchInfo ? renderMatchResult(matchInfo) : ""}</div></div></div></div></section>`;
}
function renderMatchResult(result) {
  const dims = result.dimensions || {}; const labels = result.dimension_labels || {};
  const dimBars = Object.entries(dims).map(([k,v]) => {
    return `<div class="dim-row"><div class="dim-label">${labels[k]||k}<span>${v}/5</span></div><div class="dim-bar"><span style="width:${v/5*100}%"></span></div></div>`;
  }).join("");
  return `<div class="analysis-result show"><div class="result-head"><strong>综合匹配度</strong><span class="score">${result.score}%</span></div><div class="meter"><span style="width:${result.score}%"></span></div><div class="dimensions">${dimBars}</div><ul class="tips">${result.reasons.map(x=>`<li>${escapeHtml(x)}</li>`).join("")}</ul></div>`;
}

function storesView() {
  if (state.stores.length === 0) {
    return `<section class="section"><div class="section-head"><div><h2>预约门店</h2><p>附近可预约的美甲门店</p></div></div><div class="empty">门店正在入驻中，敬请期待</div></section>`;
  }
  return `<section class="section"><div class="section-head"><div><h2>预约门店</h2><p>带着试戴结果去线下，把喜欢真正做在手上</p></div></div><div class="store-list">${state.stores.map(s=>`<article class="store-card"><div class="store-card-header"><strong>${escapeHtml(s.name)}</strong><span class="rating">${icon("star",13)} ${s.rating}</span></div><p>${escapeHtml(s.address)}<br>${escapeHtml(s.price_start)} · 支持同款定制</p><button class="btn-primary" style="width:100%" data-store-book="${escapeHtml(s.name)}">${icon("calendar-days",14)}选择门店</button></article>`).join("")}</div></section>`;
}

async function meView() {
  if (!state.user) return `<section class="section"><div class="panel" style="text-align:center;padding:70px 20px"><div style="color:var(--rose-deep);margin-bottom:12px">${icon("user-round",38)}</div><h2>登录后查看你的搭配记录</h2><p style="color:var(--muted);font-size:13px">收藏、试戴、预约和个人手部档案都会在这里汇总。</p><button class="btn-primary" data-open-auth>登录 / 注册</button></div></section>`;
  const appointments = await api(`/api/users/${state.user.id}/appointments`);
  const onboardingComplete = state.user.profile?.onboarding_status === "completed";
  return `<section class="section"><div class="panel profile-card"><div class="profile-avatar-wrap"><div class="profile-avatar">${avatarContent(state.user.name, state.user.avatar_url)}</div><input id="profile-avatar-input" type="file" accept="image/jpeg,image/png,image/webp" hidden><button class="avatar-edit-btn" id="change-avatar" title="上传或更换头像">${icon("camera",14)}${state.user.avatar_url ? "更换头像" : "上传头像"}</button></div><div class="profile-details"><h2>${escapeHtml(state.user.name)}</h2><p>${escapeHtml(state.user.email)} · ${onboardingComplete ? "你的美甲搭配档案已建立" : "随时开始建立你的美甲搭配档案"}</p><div class="stats"><div><b>${state.favorites.length}</b>收藏</div><div><b>${appointments.appointments.length}</b>预约</div><div><b>${state.posts.filter(x=>x.user_id===state.user.id).length}</b>晒图</div></div><button class="btn-secondary profile-tutorial-btn" id="restart-onboarding">${icon("sparkles",14)}${onboardingComplete ? "重新开始新手教程" : "开始美甲挑选新手教程"}</button></div></div><div class="section"><div class="section-head"><div><h2>我的收藏</h2><p>把心动款式留在灵感夹里</p></div></div><div class="grid">${state.styles.filter(x=>state.favorites.includes(x.id)).map(styleCard).join("") || `<div class="empty">还没有收藏，去社区逛逛吧</div>`}</div></div><div class="section"><div class="section-head"><div><h2>预约记录</h2><p>最近的线下美甲计划</p></div></div>${appointments.appointments.map(x=>`<div class="panel" style="padding:14px 16px;margin-bottom:10px;display:flex;justify-content:space-between;gap:12px;align-items:center"><div><strong>${escapeHtml(x.style_title)}</strong><div style="color:var(--muted);font-size:12px;margin-top:5px">${escapeHtml(x.store_name)} · ${escapeHtml(x.date)} ${escapeHtml(x.time)}</div></div><span class="chip active">${escapeHtml(x.status)}</span></div>`).join("") || `<div class="empty">暂无预约记录</div>`}</div><button class="btn-secondary" id="logout-btn">${icon("log-out",14)}退出登录</button></section>`;
}

function render() {
  const view = state.activeView;
  renderQueue = renderQueue.catch(() => {}).then(async () => {
    try {
      const content = view === "adapt" ? adaptView() : view === "community" ? communityView() : view === "tryon" ? tryonView() : view === "stores" ? storesView() : view === "me" ? await meView() : homeView();
      shell(content);
      bindStyleActions();
      bindViewActions();
    } catch (error) {
      console.error("Render failed", error);
      toast(error.message || "页面加载失败，请稍后重试");
    }
  });
  return renderQueue;
}

function bindViewActions() {
  document.querySelectorAll("[data-view]").forEach(btn => btn.addEventListener("click", () => navigate(btn.dataset.view)));
  document.querySelectorAll("[data-open-auth]").forEach(btn => btn.addEventListener("click", openAuth));
  document.querySelectorAll("[data-store-book]").forEach(btn => btn.addEventListener("click", () => openBooking(null, btn.dataset.storeBook)));
  document.querySelectorAll("[data-community-filter]").forEach(btn => btn.addEventListener("click", () => {
    state.communityFilter = btn.dataset.communityFilter || "全部";
    render();
  }));
  const upload = document.querySelector("#hand-upload"); const choose = document.querySelector("#choose-hand");
  if (upload && choose) {
    choose.addEventListener("click", () => upload.click());
    upload.addEventListener("change", async () => {
      const file = upload.files[0];
      if (!file) return;
      try {
        state.handImage = await prepareHandImage(file);
        toast("手部照片已载入，可以生成适配档案了");
        await render();
      } catch (error) {
        toast(error.message || "手部图片读取失败，请重新选择");
        upload.value = "";
      }
    });
  }
  const cameraBtn = document.querySelector("#camera-hand");
  if (cameraBtn) cameraBtn.addEventListener("click", async () => { try { const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }); document.querySelector("#camera-box").style.display = "block"; document.querySelector("#camera-video").srcObject = stream; } catch { toast("无法打开摄像头，请检查浏览器权限"); } });
  const capture = document.querySelector("#capture-hand");
  if (capture) capture.addEventListener("click", () => { const video = document.querySelector("#camera-video"); const canvas = document.createElement("canvas"); canvas.width = video.videoWidth || 640; canvas.height = video.videoHeight || 480; canvas.getContext("2d").drawImage(video,0,0,canvas.width,canvas.height); state.handImage = canvas.toDataURL("image/jpeg",.88); video.srcObject?.getTracks().forEach(track=>track.stop()); toast("已拍摄手部照片"); render(); });
  const analyze = document.querySelector("#analyze-btn");
  if (analyze) analyze.addEventListener("click", async () => {
    try {
      state.profile = { skin_tone: document.querySelector("#skin-tone").value, hand_shape: document.querySelector("#hand-shape").value, nail_shape: document.querySelector("#nail-shape").value, scene: document.querySelector("#scene").value };
      const result = await api("/api/analyze-hand", { method:"POST", body:JSON.stringify({profile:state.profile,image:state.handImage}) });
      if (state.user) {
        const saved = await api("/api/profile", { method:"POST", body:JSON.stringify({user_id:state.user.id,profile:state.profile}) });
        syncUserProfile(saved.user);
      }
      document.querySelector("#analysis-result").classList.add("show");
      document.querySelector("#analysis-result").innerHTML = `<div class="result-head"><div><strong>你的适配档案：${result.profile.style}</strong><div style="font-size:12px;color:var(--muted);margin-top:5px">${result.profile.skin_tone} · ${result.profile.hand_shape} · ${result.profile.nail_shape}</div></div><span class="score">已完成</span></div><div class="meter"><span style="width:92%"></span></div><ul class="tips">${result.tips.map(x=>`<li>${escapeHtml(x)}</li>`).join("")}</ul>`;
      toast("适配档案已更新");
    } catch (error) {
      toast(error.message || "生成适配档案失败，请稍后重试");
    }
  });
  const matchBtn = document.querySelector("#match-now");
  if (matchBtn) matchBtn.addEventListener("click", async () => {
    try {
      const style = state.selectedStyle || state.styles[0];
      const result = await api("/api/match", { method:"POST", body:JSON.stringify({style_id:style.id,profile:state.profile}) });
      state.matchResult = result;
      const dims = result.dimensions || {};
      const labels = result.dimension_labels || {};
      const dimBars = Object.entries(dims).map(([k,v]) => {
        const pct = v / 5 * 100;
        return `<div class="dim-row"><div class="dim-label">${labels[k]||k}<span>${v}/5</span></div><div class="dim-bar"><span style="width:${pct}%"></span></div></div>`;
      }).join("");
      document.querySelector("#match-result").innerHTML = `<div class="analysis-result show"><div class="result-head"><strong>综合匹配度</strong><span class="score">${result.score}%</span></div><div class="meter"><span style="width:${result.score}%"></span></div><div class="dimensions">${dimBars}</div><ul class="tips">${result.reasons.map(x=>`<li>${escapeHtml(x)}</li>`).join("")}</ul><div style="margin-top:12px;display:flex;gap:8px"><button class="btn-secondary" id="share-match" style="flex:1">${icon("share-2",14)}分享评分</button><button class="btn-primary" id="book-from-match" style="flex:1">${icon("calendar-days",14)}去预约</button></div></div>`;
      document.querySelector("#book-from-match")?.addEventListener("click", openBooking);
      document.querySelector("#share-match")?.addEventListener("click", () => shareContent("style", style, result.score));
    } catch (error) {
      toast(error.message || "匹配评分生成失败，请稍后重试");
    }
  });
  const bookTry = document.querySelector("#book-from-tryon"); if (bookTry) bookTry.addEventListener("click", openBooking);
  const shareTryon = document.querySelector("#share-tryon"); if (shareTryon) shareTryon.addEventListener("click", () => { const style = state.selectedStyle || state.styles[0]; shareTryonResult(style); });
  document.querySelectorAll("#publish-post, #sidebar-publish").forEach(btn => btn.addEventListener("click", openPublish));
  const avatarInput = document.querySelector("#profile-avatar-input");
  document.querySelector("#change-avatar")?.addEventListener("click", () => avatarInput?.click());
  avatarInput?.addEventListener("change", async () => {
    const file = avatarInput.files[0];
    if (!file) return;
    try {
      const avatarData = await prepareAvatar(file);
      const result = await api("/api/profile/avatar", { method: "POST", body: JSON.stringify({ avatar_data: avatarData }) });
      state.user = result.user;
      localStorage.setItem("md_user", JSON.stringify(state.user));
      state.posts.forEach(post => {
        if (post.user_id === state.user.id) post.user_avatar_url = state.user.avatar_url;
      });
      toast("头像已更新");
      await render();
    } catch (error) {
      toast(error.message || "头像更新失败，请稍后重试");
      avatarInput.value = "";
    }
  });
  const logout = document.querySelector("#logout-btn"); if (logout) logout.addEventListener("click", async () => { await api("/api/auth/logout", { method:"POST", body:"{}" }).catch(() => {}); localStorage.removeItem("md_user"); localStorage.removeItem("md_token"); state.user=null; state.token=""; state.favorites=[]; toast("\u5df2\u9000\u51fa\u767b\u5f55"); navigate("home"); });
  document.querySelector("#restart-onboarding")?.addEventListener("click", () => openOnboarding({ restart: true }));

  // Canvas 虚拟试戴渲染与输入源
  const tryonCanvas = document.querySelector("#tryon-canvas");
  if (tryonCanvas) {
    tryonRuntime.resizeObserver?.disconnect();
    tryonRuntime.resizeObserver = new ResizeObserver(() => redrawTryonScene());
    tryonRuntime.resizeObserver.observe(document.querySelector("#tryon-stage"));
    if (state.handImage) renderTryonImage(tryonCanvas);
    else renderTryonPlaceholder(tryonCanvas);
    document.querySelector("#nail-color")?.addEventListener("input", redrawTryonScene);
    document.querySelector("#tryon-shape")?.addEventListener("change", redrawTryonScene);
    document.querySelector("#tryon-length")?.addEventListener("input", redrawTryonScene);
  }
  const tryonFile = document.querySelector("#tryon-file");
  document.querySelector("#tryon-upload")?.addEventListener("click", () => tryonFile?.click());
  tryonFile?.addEventListener("change", async () => {
    const file = tryonFile.files[0];
    if (!file) return;
    stopTryonCamera();
    setTryonStatus("正在读取手部图片...", "loading");
    setTryonBusy(true);
    try {
      const handImage = await prepareHandImage(file);
      stopTryonCamera();
      state.handImage = handImage;
      tryonRuntime.mode = "image";
      toast("手部图片已载入，正在识别双手");
      await render();
    } catch (error) {
      setTryonStatus(error.message || "图片读取失败，请重新选择", "error");
      setTryonBusy(false);
      tryonFile.value = "";
    }
  });
  document.querySelector("#tryon-camera")?.addEventListener("click", startTryonCamera);
  document.querySelector("#tryon-close-camera")?.addEventListener("click", async () => {
    stopTryonCamera();
    toast("摄像头已关闭");
    await render();
  });

  // 搜索功能
  const searchInput = document.querySelector("#search-input");
  const searchBtn2 = document.querySelector("#search-btn");
  if (searchInput) {
    let searchTimer;
    searchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(async () => {
        const q = searchInput.value.trim();
        if (!q) { hideSearchDropdown(); return; }
        // 优先调用后端搜索API
        try {
          const data = await api(`/api/search?q=${encodeURIComponent(q)}`);
          showSearchDropdown(data.results || [], q, data.douyin_url);
        } catch(e) {
          showSearchDropdown([], q);
        }
      }, 250);
    });
    searchInput.addEventListener("focus", () => {
      if (searchInput.value.trim()) searchInput.dispatchEvent(new Event("input"));
    });
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const q = searchInput.value.trim();
        if (q) window.open(`https://www.douyin.com/search/${encodeURIComponent(q+" 美甲")}?type=general`, "_blank");
      }
    });
  }
  if (searchBtn2) {
    searchBtn2.addEventListener("click", () => searchInput?.dispatchEvent(new Event("input")));
  }
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#search-box")) hideSearchDropdown();
  });

  // 社区帖子点赞
  document.querySelectorAll("[data-like-post]").forEach(btn => btn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!state.user) return openAuth();
    try {
      const result = await api("/api/community/posts/like", { method: "POST", body: JSON.stringify({ post_id: Number(btn.dataset.likePost) }) });
      if (!result.added) return toast("你已经点过赞了");
      const post = state.posts.find(item => item.id === Number(btn.dataset.likePost));
      if (post) post.likes = Number(post.likes || 0) + 1;
      const countEl = btn.querySelector("span"); if (countEl) countEl.textContent = Number(countEl.textContent) + 1;
      btn.classList.add("liked");
      toast("已点赞");
    } catch (error) {
      toast(error.message || "点赞失败，请稍后重试");
    }
  }));

  // 查看帖子评论
  document.querySelectorAll("[data-comment-post]").forEach(btn => btn.addEventListener("click", async (e) => {
    e.stopPropagation();
    try {
      await openPostDetail(Number(btn.dataset.commentPost));
    } catch (error) {
      toast(error.message || "加载评论失败，请稍后重试");
    }
  }));
}

function showSearchDropdown(results, query, douyinUrl) {
  const dd = document.querySelector("#search-dropdown");
  if (!dd) return;
  if (!results || results.length === 0) {
    dd.style.display = "block";
    dd.innerHTML = `<div class="sd-empty">未找到匹配款式<br><small>试试：法式 显白 通勤 短甲 粉色 猫眼</small></div>
      <div class="sd-footer"><button id="douyin-search-btn">🔍 在抖音搜索"${escapeHtml(query)}"美甲</button></div>`;
  } else {
    dd.style.display = "block";
    dd.innerHTML = results.map((s, i) => {
      const imgSrc = s.image_url || "";
      return `<div class="sd-item" data-search-select="${s.id}">
        <img class="sd-img" src="${imgSrc}" style="--c1:${s.color_a};--c2:${s.color_b}" onerror="this.style.background='linear-gradient(145deg,'+this.style.getPropertyValue('--c1')+','+this.style.getPropertyValue('--c2')+')';this.style.display='none'">
        <div class="sd-info">
          <strong>${escapeHtml(s.title)}</strong>
          <div class="sd-meta">${escapeHtml(s.category)} · ${(s.tags||[]).slice(0,2).join(" · ")} · ¥${escapeHtml(s.price)}</div>
          <span class="sd-match">匹配度 ${s.match_score||70}%</span>
        </div>
      </div>`;
    }).join("") + `<div class="sd-footer"><button id="douyin-search-btn">🔍 在抖音搜索更多"${escapeHtml(query)}"美甲</button></div>`;
  }
  document.querySelectorAll("[data-search-select]").forEach(el => {
    el.addEventListener("click", () => {
      const id = Number(el.dataset.searchSelect);
      state.selectedStyle = state.styles.find(s => s.id === id);
      hideSearchDropdown();
      const si = document.querySelector("#search-input");
      if (si) si.value = "";
      navigate("tryon");
    });
  });
  document.querySelector("#douyin-search-btn")?.addEventListener("click", () => {
    const targetUrl = douyinUrl || `https://www.douyin.com/search/${encodeURIComponent(query+" 美甲")}?type=general`;
    window.open(targetUrl, "_blank");
  });
}
function hideSearchDropdown() {
  const dd = document.querySelector("#search-dropdown");
  if (dd) dd.style.display = "none";
}

function openAuth() {
  const modal = document.querySelector("#modal"); const box = document.querySelector("#modal-content"); modal.classList.add("open");
  box.innerHTML = `<div class="modal-head"><h3>欢迎来到 Bloom</h3><button class="close" id="close-modal">${icon("x",17)}</button></div><div class="tabs"><button class="active" data-auth-tab="login">登录</button><button data-auth-tab="register">注册</button></div><div id="auth-form"></div>`;
  renderAuthForm("login"); renderIcons(); document.querySelector("#close-modal").addEventListener("click", closeModal); document.querySelectorAll("[data-auth-tab]").forEach(btn=>btn.addEventListener("click",()=>{document.querySelectorAll("[data-auth-tab]").forEach(x=>x.classList.remove("active"));btn.classList.add("active");renderAuthForm(btn.dataset.authTab);}));
}
function renderAuthForm(mode) {
  const register = mode === "register";
  document.querySelector("#auth-form").innerHTML = `${register ? `<div class="field" style="margin-bottom:11px"><label>昵称</label><input id="auth-name" placeholder="给自己起个好听的名字"></div><div class="avatar-picker"><div class="avatar-picker-preview" id="register-avatar-preview">${icon("user-round",24)}</div><div><strong>设置头像</strong><small>可跳过，注册后也能在“我的”页面更换</small></div><input id="register-avatar-input" type="file" accept="image/jpeg,image/png,image/webp" hidden><button class="btn-secondary" id="choose-register-avatar" type="button">${icon("image-plus",14)}上传头像</button><button class="btn-ghost" id="remove-register-avatar" type="button" hidden>移除</button></div>` : ""}<div class="field" style="margin-bottom:11px"><label>邮箱</label><input id="auth-email" type="email" placeholder="you@example.com"></div><div class="field"><label>密码</label><input id="auth-password" type="password" placeholder="至少 8 位字符"></div><button class="btn-primary" id="auth-submit" style="width:100%;margin-top:16px">${register ? "创建我的搭配档案" : "登录 Bloom"}</button><p style="font-size:11px;color:var(--muted);line-height:1.6;margin:12px 0 0">账号资料会安全保存在服务端；头像可在注册后随时更换。</p>`;

  let avatarData = "";
  const avatarInput = document.querySelector("#register-avatar-input");
  const avatarPreview = document.querySelector("#register-avatar-preview");
  const removeAvatar = document.querySelector("#remove-register-avatar");
  document.querySelector("#choose-register-avatar")?.addEventListener("click", () => avatarInput?.click());
  removeAvatar?.addEventListener("click", () => {
    avatarData = "";
    avatarInput.value = "";
    avatarPreview.innerHTML = icon("user-round", 24);
    removeAvatar.hidden = true;
  });
  avatarInput?.addEventListener("change", async () => {
    const file = avatarInput.files[0];
    if (!file) return;
    try {
      avatarData = await prepareAvatar(file);
      avatarPreview.innerHTML = `<img src="${avatarData}" alt="头像预览">`;
      removeAvatar.hidden = false;
    } catch (error) {
      avatarData = "";
      avatarInput.value = "";
      toast(error.message || "头像处理失败，请重新选择");
    }
  });
  document.querySelector("#auth-submit").addEventListener("click", async () => {
    try {
      const payload = { email: document.querySelector("#auth-email").value, password: document.querySelector("#auth-password").value };
      if (register) {
        payload.name = document.querySelector("#auth-name").value;
        if (avatarData) payload.avatar_data = avatarData;
      }
      const result = await api(register ? "/api/auth/register" : "/api/auth/login", { method:"POST", body:JSON.stringify(payload) });
      state.user = result.user;
      state.token = result.token;
      localStorage.setItem("md_user", JSON.stringify(state.user));
      localStorage.setItem("md_token", state.token);
      closeModal();
      if (!register) toast("登录成功");
      await loadData();
      await render();
      if (register) openOnboarding();
    } catch (error) {
      toast(error.message || "登录失败，请稍后重试");
    }
  });
}
function closeModal(){document.querySelector("#modal")?.classList.remove("open");}
function openBooking(style = state.selectedStyle, storeName = "花漾美甲·中心店"){ if(!state.user)return openAuth(); style=style||state.styles[0]; const modal=document.querySelector("#modal"),box=document.querySelector("#modal-content"); modal.classList.add("open"); box.innerHTML=`<div class="modal-head"><h3>预约 ${escapeHtml(style.title)}</h3><button class="close" id="close-modal">${icon("x",17)}</button></div><p style="color:var(--muted);font-size:12px;line-height:1.6">选择你方便的门店和时间，预约信息会带上这款美甲方案。</p><div class="field" style="margin:12px 0"><label>门店</label><select id="book-store"><option>${escapeHtml(storeName)}</option><option>Luna Nail Studio</option><option>粉雾美学工作室</option></select></div><div class="form-grid"><div class="field"><label>日期</label><input id="book-date" type="date"></div><div class="field"><label>时间</label><select id="book-time"><option>10:00</option><option>13:30</option><option>16:00</option><option>19:00</option></select></div></div><div class="field" style="margin-top:12px"><label>备注</label><textarea id="book-note" rows="3" placeholder="例如：希望做成中短方圆甲"></textarea></div><button class="btn-primary" id="book-submit" style="width:100%;margin-top:14px">${icon("calendar-check",15)}提交预约</button>`; renderIcons(); document.querySelector("#close-modal").addEventListener("click",closeModal); document.querySelector("#book-submit").addEventListener("click",async()=>{try{await api("/api/appointments",{method:"POST",body:JSON.stringify({user_id:state.user.id,style_id:style.id,store_name:document.querySelector("#book-store").value,date:document.querySelector("#book-date").value||"待定",time:document.querySelector("#book-time").value,note:document.querySelector("#book-note").value})});closeModal();toast("预约已提交，门店会尽快联系你");}catch(e){toast(e.message)}});}
function openPublish() {
  if (!state.user) return openAuth();
  const modal = document.querySelector("#modal"), box = document.querySelector("#modal-content");
  modal.classList.add("open");
  const categories = ["猫眼","新中式","短甲友好","法式","显白","极简","新娘","果冻","花卉","几何","探店"];
  box.innerHTML = `<div class="modal-head"><h3>发布我的美甲</h3><button class="close" id="close-modal">${icon("x",17)}</button></div>
    <div class="field"><label>标题</label><input id="post-title" placeholder="例如：冰透猫眼短甲客照"></div>
    <div class="form-grid" style="margin-top:11px"><div class="field"><label>主题</label><select id="post-category">${categories.map(x=>`<option>${x}</option>`).join("")}</select></div><div class="field"><label>标签</label><input id="post-tags" placeholder="显白, 通勤, 短甲"></div></div>
    <div class="field" style="margin-top:11px"><label>图片</label><input id="post-image" type="file" accept="image/*"><small>建议上传自然光下的清晰手部客照</small></div>
    <div class="field" style="margin-top:11px"><label>分享几句</label><textarea id="post-body" rows="3" placeholder="可以分享价格、门店、甲型、保持时间和踩坑点"></textarea></div>
    <button class="btn-primary" id="post-submit" style="width:100%;margin-top:14px">${icon("send",15)}发布到社区</button>`;
  renderIcons();
  document.querySelector("#close-modal").addEventListener("click", closeModal);
  document.querySelector("#post-submit").addEventListener("click", () => {
    const file = document.querySelector("#post-image").files[0];
    if (!file) return toast("请先选择一张图片");
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const compressed = await compressImage(reader.result, 400);
        const tags = document.querySelector("#post-tags").value.split(/[,，\s]+/).map(x=>x.trim()).filter(Boolean).slice(0,6);
        await api("/api/community/posts", { method:"POST", body:JSON.stringify({ user_id:state.user.id, title:document.querySelector("#post-title").value.trim() || "我的新美甲", body:document.querySelector("#post-body").value.trim(), image_data:compressed, category:document.querySelector("#post-category").value, tags }) });
        closeModal(); toast("发布成功"); await loadData(); render();
      } catch (e) { toast(e.message); }
    };
    reader.readAsDataURL(file);
  });
}

async function openPostDetail(postId) {
  const post = state.posts.find(p => p.id === postId);
  if (!post) return;
  const comments = await api(`/api/community/posts/${postId}/comments`).catch(() => ({ comments: [] }));
  const modal = document.querySelector("#modal"), box = document.querySelector("#modal-content");
  const tags = (post.tags || []).map(tag => `<span>#${escapeHtml(tag)}</span>`).join("");
  const source = /^https?:\/\//.test(post.source_url || "") ? `<a class="detail-source" href="${escapeHtml(post.source_url)}" target="_blank" rel="noopener noreferrer">${icon("external-link",13)} 查看国内素材检索来源</a><small>${escapeHtml(post.source_license || "")}</small>` : "";
  modal.classList.add("open");
  box.innerHTML = `<div class="modal-head"><div><span class="eyebrow">${escapeHtml(post.category || "美甲灵感")}</span><h3 style="margin-top:8px">帖子详情</h3></div><button class="close" id="close-modal">${icon("x",17)}</button></div>
    <div class="post-detail-scroll">
      <img class="post-detail-image" src="${escapeHtml(post.image_data)}" alt="${escapeHtml(post.title)}">
      <div class="post-detail-author"><span class="post-avatar">${avatarContent(post.user_name || "美", post.user_avatar_url)}</span><div><strong>${escapeHtml(post.user_name || "搭配师用户")}</strong><small>${post.editorial ? "国内美甲灵感采编" : "真实用户分享"}</small></div></div>
      <h3 class="post-detail-title">${escapeHtml(post.title)}</h3>
      <p class="post-detail-copy">${escapeHtml(post.body || "")}</p>
      ${tags ? `<div class="post-tags">${tags}</div>` : ""}
      ${source ? `<div class="post-detail-source">${source}</div>` : ""}
      <div class="post-detail-stats">${icon("heart",12)} ${post.likes || 0} 赞 · ${comments.comments.length} 条评论</div>
      <div class="comment-list"><h4>评论</h4>
        ${comments.comments.map(c => `<div class="comment-item"><span class="comment-avatar">${avatarContent(c.user_name || "美", c.user_avatar_url)}</span><div><strong>${escapeHtml(c.user_name)}</strong><p>${escapeHtml(c.content)}</p></div></div>`).join("") || '<p class="comment-empty">暂无评论，来第一个评论吧</p>'}
      </div>
      ${state.user ? `<div class="comment-compose"><input id="comment-input" placeholder="写下你的评论..."><button class="btn-primary" id="submit-comment">${icon("send",14)}</button></div>` : ""}
    </div>`;
  renderIcons();
  document.querySelector("#close-modal")?.addEventListener("click", closeModal);
  document.querySelector("#submit-comment")?.addEventListener("click", async () => {
    const content = document.querySelector("#comment-input").value.trim();
    if (!content) return toast("请输入评论内容");
    try {
      await api("/api/community/comments", { method: "POST", body: JSON.stringify({ user_id: state.user.id, post_id: postId, content }) });
      toast("评论已发布");
      await openPostDetail(postId);
    } catch (error) {
      toast(error.message || "评论发布失败，请稍后重试");
    }
  });
}

// MediaPipe 双手识别与 Canvas 虚拟试戴
function setTryonStatus(message, tone = "neutral") {
  const status = document.querySelector("#tryon-status");
  if (!status || (status.textContent === message && status.dataset.tone === tone)) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function setTryonBusy(busy) {
  ["#tryon-camera", "#tryon-upload"].forEach(selector => {
    const button = document.querySelector(selector);
    if (button) button.disabled = busy;
  });
}

function canvasMetrics(canvas) {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width || canvas.parentElement?.clientWidth || 640));
  const height = Math.max(1, Math.round(rect.height || width * 0.75));
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const pixelWidth = Math.round(width * ratio);
  const pixelHeight = Math.round(height * ratio);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width, height };
}

function renderTryonPlaceholder(canvas) {
  const { ctx, width, height } = canvasMetrics(canvas);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbefee";
  ctx.fillRect(0, 0, width, height);
  tryonRuntime.hasFrame = false;
}

function sourceDimensions(source) {
  return {
    width: source.videoWidth || source.naturalWidth || source.width || 1,
    height: source.videoHeight || source.naturalHeight || source.height || 1,
  };
}

function sourceRect(source, width, height, fit = "contain") {
  const sourceSize = sourceDimensions(source);
  const scale = fit === "cover"
    ? Math.max(width / sourceSize.width, height / sourceSize.height)
    : Math.min(width / sourceSize.width, height / sourceSize.height);
  const drawWidth = sourceSize.width * scale;
  const drawHeight = sourceSize.height * scale;
  return {
    x: (width - drawWidth) / 2,
    y: (height - drawHeight) / 2,
    width: drawWidth,
    height: drawHeight,
  };
}

function drawNailPath(ctx, width, height, shape) {
  ctx.beginPath();
  if (shape === "almond") {
    ctx.moveTo(0, -height / 2);
    ctx.bezierCurveTo(width * 0.44, -height * 0.32, width * 0.5, height * 0.28, 0, height / 2);
    ctx.bezierCurveTo(-width * 0.5, height * 0.28, -width * 0.44, -height * 0.32, 0, -height / 2);
  } else if (shape === "stiletto") {
    ctx.moveTo(0, -height / 2);
    ctx.lineTo(width / 2.35, height * 0.34);
    ctx.quadraticCurveTo(width / 2.5, height / 2, 0, height / 2);
    ctx.quadraticCurveTo(-width / 2.5, height / 2, -width / 2.35, height * 0.34);
    ctx.closePath();
  } else if (shape === "round") {
    ctx.ellipse(0, 0, width / 2, height / 2.15, 0, 0, Math.PI * 2);
  } else {
    ctx.roundRect(-width / 2, -height / 2, width, height, Math.max(2, width / 5));
  }
}

function drawNail(ctx, nail, color, shape) {
  ctx.save();
  ctx.translate(nail.x, nail.y);
  ctx.rotate(nail.angle);
  drawNailPath(ctx, nail.width, nail.height, shape);
  const fill = ctx.createLinearGradient(0, -nail.height / 2, 0, nail.height / 2);
  fill.addColorStop(0, lightenColor(color, 36));
  fill.addColorStop(0.5, color);
  fill.addColorStop(1, darkenColor(color, 22));
  ctx.fillStyle = fill;
  ctx.shadowColor = "rgba(55,25,35,.22)";
  ctx.shadowBlur = Math.max(2, nail.width * 0.16);
  ctx.fill();
  ctx.shadowBlur = 0;
  const highlight = ctx.createLinearGradient(-nail.width / 2, -nail.height / 2, nail.width / 3, 0);
  highlight.addColorStop(0, "rgba(255,255,255,.48)");
  highlight.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = highlight;
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,.62)";
  ctx.lineWidth = 0.9;
  ctx.stroke();
  ctx.restore();
}

function landmarkPoint(point, rect, mirror) {
  return {
    x: rect.x + (mirror ? 1 - point.x : point.x) * rect.width,
    y: rect.y + point.y * rect.height,
  };
}

function nailFromLandmarks(landmarks, tipIndex, dipIndex, rect, mirror, lengthScale) {
  const tip = landmarkPoint(landmarks[tipIndex], rect, mirror);
  const dip = landmarkPoint(landmarks[dipIndex], rect, mirror);
  const dx = tip.x - dip.x;
  const dy = tip.y - dip.y;
  const segment = Math.max(1, Math.hypot(dx, dy));
  const thumbScale = tipIndex === 4 ? 1.08 : 1;
  return {
    x: tip.x - dx * 0.3,
    y: tip.y - dy * 0.3,
    width: Math.max(7, Math.min(34, segment * 0.46 * thumbScale)),
    height: Math.max(13, Math.min(68, segment * 0.74 * lengthScale * thumbScale)),
    angle: Math.atan2(dy, dx) + Math.PI / 2,
  };
}

function drawTryonScene(canvas, source, hands = [], options = {}) {
  if (!canvas || !source) return;
  const { mirror = false, fallback = false, fit = "contain" } = options;
  const { ctx, width, height } = canvasMetrics(canvas);
  const rect = sourceRect(source, width, height, fit);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#2b2528";
  ctx.fillRect(0, 0, width, height);
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, width, height);
  ctx.clip();
  if (mirror) {
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(source, width - rect.x - rect.width, rect.y, rect.width, rect.height);
  } else {
    ctx.drawImage(source, rect.x, rect.y, rect.width, rect.height);
  }
  ctx.restore();

  const style = state.selectedStyle || state.styles[0] || { title: "虚拟试戴", color_a: "#a9605a" };
  const color = normalizeHexColor(document.querySelector("#nail-color")?.value || style.color_a);
  const shape = document.querySelector("#tryon-shape")?.value || "square";
  const lengthScale = parseFloat(document.querySelector("#tryon-length")?.value || "1");
  const fingerPairs = [[4, 3], [8, 7], [12, 11], [16, 15], [20, 19]];

  hands.forEach(hand => {
    fingerPairs.forEach(([tipIndex, dipIndex]) => {
      drawNail(ctx, nailFromLandmarks(hand.landmarks, tipIndex, dipIndex, rect, mirror, lengthScale), color, shape);
    });
  });

  if (fallback) {
    const fallbackNails = [
      { x: .22, y: .16, width: 24, height: 48, angle: -.22 },
      { x: .36, y: .10, width: 24, height: 51, angle: -.1 },
      { x: .50, y: .08, width: 24, height: 52, angle: .04 },
      { x: .64, y: .11, width: 23, height: 49, angle: .18 },
      { x: .76, y: .22, width: 21, height: 43, angle: .46 },
    ];
    fallbackNails.forEach(nail => drawNail(ctx, {
      x: rect.x + rect.width * nail.x,
      y: rect.y + rect.height * nail.y,
      width: nail.width * Math.max(.72, Math.min(1.35, rect.width / 520)),
      height: nail.height * lengthScale * Math.max(.72, Math.min(1.35, rect.width / 520)),
      angle: nail.angle,
    }, color, shape));
  }

  ctx.fillStyle = "rgba(255,255,255,.9)";
  ctx.font = "600 11px 'Noto Sans SC'";
  ctx.fillText(`Bloom 试戴 · ${style.title}`, 12, height - 12);
  tryonRuntime.hasFrame = true;
  const empty = document.querySelector("#tryon-empty");
  if (empty) empty.hidden = true;
}

function normalizedHands(result, smooth = false) {
  const nextHands = (result?.landmarks || []).map((landmarks, index) => {
    const handedness = result.handednesses?.[index]?.[0];
    const label = handedness?.categoryName || `hand-${index}`;
    if (!smooth) return { label, landmarks };
    const previous = tryonRuntime.smoothedHands.get(label);
    const alpha = 0.42;
    const points = previous
      ? landmarks.map((point, pointIndex) => ({
          x: previous[pointIndex].x + (point.x - previous[pointIndex].x) * alpha,
          y: previous[pointIndex].y + (point.y - previous[pointIndex].y) * alpha,
          z: previous[pointIndex].z + (point.z - previous[pointIndex].z) * alpha,
        }))
      : landmarks.map(point => ({ ...point }));
    tryonRuntime.smoothedHands.set(label, points);
    return { label, landmarks: points };
  });
  return nextHands;
}

async function ensureHandLandmarker() {
  if (tryonRuntime.landmarker) return tryonRuntime.landmarker;
  if (tryonRuntime.landmarkerPromise) return tryonRuntime.landmarkerPromise;
  tryonRuntime.landmarkerPromise = (async () => {
    const { FilesetResolver, HandLandmarker } = await import(HAND_LANDMARKER_MODULE);
    const vision = await FilesetResolver.forVisionTasks(HAND_LANDMARKER_WASM);
    const options = {
      baseOptions: { modelAssetPath: HAND_LANDMARKER_MODEL, delegate: "GPU" },
      runningMode: "IMAGE",
      numHands: 2,
      minHandDetectionConfidence: 0.5,
      minHandPresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    };
    try {
      tryonRuntime.landmarker = await HandLandmarker.createFromOptions(vision, options);
    } catch {
      tryonRuntime.landmarker = await HandLandmarker.createFromOptions(vision, {
        ...options,
        baseOptions: { modelAssetPath: HAND_LANDMARKER_MODEL, delegate: "CPU" },
      });
    }
    tryonRuntime.runningMode = "IMAGE";
    return tryonRuntime.landmarker;
  })().catch(error => {
    tryonRuntime.landmarkerPromise = null;
    throw error;
  });
  return tryonRuntime.landmarkerPromise;
}

async function setLandmarkerMode(mode) {
  const landmarker = await ensureHandLandmarker();
  if (tryonRuntime.runningMode !== mode) {
    await landmarker.setOptions({ runningMode: mode });
    tryonRuntime.runningMode = mode;
  }
  return landmarker;
}

async function renderTryonImage(canvas) {
  const session = ++tryonRuntime.session;
  tryonRuntime.mode = "image";
  tryonRuntime.staticImage = null;
  tryonRuntime.staticHands = [];
  tryonRuntime.staticFallback = false;
  setTryonBusy(true);
  setTryonStatus("正在加载手部识别模型...", "loading");
  try {
    const image = await loadImage(state.handImage);
    if (session !== tryonRuntime.session || !document.contains(canvas)) return;
    tryonRuntime.staticImage = image;
    drawTryonScene(canvas, image);
    const landmarker = await setLandmarkerMode("IMAGE");
    if (session !== tryonRuntime.session || !document.contains(canvas)) return;
    const hands = normalizedHands(landmarker.detect(image));
    tryonRuntime.staticHands = hands;
    tryonRuntime.staticFallback = hands.length === 0;
    drawTryonScene(canvas, image, hands, { fallback: tryonRuntime.staticFallback });
    setTryonStatus(
      hands.length ? `已识别 ${hands.length} 只手 · 图片试戴已就绪` : "未识别到清晰手部，已启用简易预览",
      hands.length ? "success" : "warning",
    );
  } catch (error) {
    if (session !== tryonRuntime.session || !document.contains(canvas)) return;
    console.error("Hand image detection failed", error);
    if (tryonRuntime.staticImage) {
      tryonRuntime.staticFallback = true;
      drawTryonScene(canvas, tryonRuntime.staticImage, [], { fallback: true });
    }
    setTryonStatus("识别模型加载失败，已启用简易预览", "error");
  } finally {
    if (session === tryonRuntime.session) setTryonBusy(false);
  }
}

function redrawTryonScene() {
  const canvas = document.querySelector("#tryon-canvas");
  if (!canvas) return;
  if (tryonRuntime.mode === "camera") {
    const video = document.querySelector("#tryon-video");
    if (video?.readyState >= 2) drawTryonScene(canvas, video, tryonRuntime.lastHands, { mirror: true, fit: "cover" });
  } else if (tryonRuntime.staticImage) {
    drawTryonScene(canvas, tryonRuntime.staticImage, tryonRuntime.staticHands, { fallback: tryonRuntime.staticFallback });
  } else {
    renderTryonPlaceholder(canvas);
  }
}

function cameraErrorMessage(error) {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) return "当前环境无法使用摄像头，请通过 HTTPS 或 localhost 打开页面";
  if (error?.name === "NotAllowedError" || error?.name === "SecurityError") return "摄像头权限被拒绝，请在浏览器地址栏中允许访问";
  if (error?.name === "NotFoundError" || error?.name === "OverconstrainedError") return "没有找到可用的前置摄像头";
  if (error?.name === "NotReadableError" || error?.name === "AbortError") return "摄像头可能正被其他应用占用，请关闭后重试";
  return "摄像头启动失败，请检查设备和浏览器权限";
}

function startCameraLoop(canvas, video, landmarker, session) {
  const loop = timestamp => {
    if (session !== tryonRuntime.session || tryonRuntime.mode !== "camera" || !document.contains(canvas)) return;
    if (video.readyState >= 2) {
      if (!tryonRuntime.detectionFailed && timestamp - tryonRuntime.lastDetectionAt >= 33 && video.currentTime !== tryonRuntime.lastVideoTime) {
        try {
          const hands = normalizedHands(landmarker.detectForVideo(video, timestamp), true);
          tryonRuntime.lastDetectionAt = timestamp;
          tryonRuntime.lastVideoTime = video.currentTime;
          if (hands.length) {
            tryonRuntime.lastHands = hands;
            tryonRuntime.lastHandSeenAt = timestamp;
            setTryonStatus(`已识别 ${hands.length} 只手 · 实时跟随中`, "success");
          } else if (timestamp - tryonRuntime.lastHandSeenAt > 250) {
            tryonRuntime.lastHands = [];
            tryonRuntime.smoothedHands.clear();
            setTryonStatus("未检测到手，请让手背朝向镜头并自然展开", "warning");
          }
        } catch (error) {
          console.error("Live hand detection failed", error);
          tryonRuntime.detectionFailed = true;
          tryonRuntime.lastHands = [];
          setTryonStatus("实时识别暂时不可用，可上传图片继续试戴", "error");
        }
      }
      drawTryonScene(canvas, video, tryonRuntime.lastHands, { mirror: true, fit: "cover" });
    }
    tryonRuntime.frameRequest = requestAnimationFrame(loop);
  };
  tryonRuntime.frameRequest = requestAnimationFrame(loop);
}

async function startTryonCamera() {
  const canvas = document.querySelector("#tryon-canvas");
  const video = document.querySelector("#tryon-video");
  if (!canvas || !video) return;
  stopTryonCamera();
  const session = ++tryonRuntime.session;
  setTryonBusy(true);
  setTryonStatus("正在请求前置摄像头权限...", "loading");
  try {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new DOMException("Unsupported camera context", "SecurityError");
    const modelPromise = ensureHandLandmarker();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    if (session !== tryonRuntime.session) {
      stream.getTracks().forEach(track => track.stop());
      return;
    }
    tryonRuntime.stream = stream;
    tryonRuntime.mode = "camera";
    tryonRuntime.lastHands = [];
    tryonRuntime.smoothedHands.clear();
    tryonRuntime.lastVideoTime = -1;
    tryonRuntime.lastDetectionAt = 0;
    tryonRuntime.lastHandSeenAt = 0;
    tryonRuntime.detectionFailed = false;
    video.srcObject = stream;
    await video.play();
    drawTryonScene(canvas, video, [], { mirror: true, fit: "cover" });
    document.querySelector("#tryon-close-camera")?.removeAttribute("hidden");
    setTryonStatus("正在加载手部识别模型...", "loading");
    const landmarker = await modelPromise;
    if (session !== tryonRuntime.session) return;
    await setLandmarkerMode("VIDEO");
    if (session !== tryonRuntime.session) return;
    setTryonBusy(false);
    setTryonStatus("请将双手放入画面，手背朝向镜头", "neutral");
    startCameraLoop(canvas, video, landmarker, session);
  } catch (error) {
    console.error("Camera startup failed", error);
    stopTryonCamera();
    if (state.handImage) renderTryonImage(canvas);
    else renderTryonPlaceholder(canvas);
    setTryonStatus(cameraErrorMessage(error), "error");
    setTryonBusy(false);
  }
}

function stopTryonCamera(message = "") {
  tryonRuntime.session += 1;
  if (tryonRuntime.frameRequest) cancelAnimationFrame(tryonRuntime.frameRequest);
  tryonRuntime.frameRequest = 0;
  tryonRuntime.stream?.getTracks().forEach(track => track.stop());
  tryonRuntime.stream = null;
  const video = document.querySelector("#tryon-video");
  if (video) {
    video.pause();
    video.srcObject = null;
  }
  tryonRuntime.mode = state.handImage ? "image" : "idle";
  tryonRuntime.lastHands = [];
  tryonRuntime.smoothedHands.clear();
  tryonRuntime.lastVideoTime = -1;
  document.querySelector("#tryon-close-camera")?.setAttribute("hidden", "");
  setTryonBusy(false);
  if (message) setTryonStatus(message, "neutral");
}

function cleanupTryonView() {
  stopTryonCamera();
  tryonRuntime.resizeObserver?.disconnect();
  tryonRuntime.resizeObserver = null;
}

// 颜色工具函数
function normalizeHexColor(hex, fallback = "#a9605a") {
  const value = String(hex || "").trim().toLowerCase();
  if (/^#[0-9a-f]{6}$/.test(value)) return value;
  if (/^#[0-9a-f]{3}$/.test(value)) return `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`;
  return fallback;
}

function lightenColor(hex, percent) {
  const num = parseInt(normalizeHexColor(hex).replace("#", ""), 16);
  const r = Math.min(255, (num >> 16) + Math.round(2.55 * percent));
  const g = Math.min(255, ((num >> 8) & 0xFF) + Math.round(2.55 * percent));
  const b = Math.min(255, (num & 0xFF) + Math.round(2.55 * percent));
  return `rgb(${r},${g},${b})`;
}
function darkenColor(hex, percent) {
  const num = parseInt(normalizeHexColor(hex).replace("#", ""), 16);
  const r = Math.max(0, (num >> 16) - Math.round(2.55 * percent));
  const g = Math.max(0, ((num >> 8) & 0xFF) - Math.round(2.55 * percent));
  const b = Math.max(0, (num & 0xFF) - Math.round(2.55 * percent));
  return `rgb(${r},${g},${b})`;
}

async function boot(){
  startThree();
  try {
    await loadData();
  } catch(e) {
    console.warn("API 连接失败，使用演示数据", e);
    loadDemoData();
    toast("📡 正在使用离线演示模式");
  }
  await render();
}

function loadDemoData() {
  state.styles = [
    { id:1, title:"樱粉奶油法式", category:"法式", tags:["法式","短甲友好","温柔"], scene:"通勤", skin_tones:["暖黄皮","自然肤色"], nail_shapes:["圆甲","方圆甲"], price:"79-159", color_a:"#f9c8d8", color_b:"#fff5f7", skin_brightness:4, hand_shape_fit:3, daily_convenience:5, maintenance_ease:4, style_match:4, likes:128, image_url:"assets/photos/photo_001.svg", gender_suitability:"female" },
    { id:2, title:"玫瑰猫眼", category:"猫眼", tags:["猫眼","显白","高级感"], scene:"约会", skin_tones:["冷白皮","自然肤色"], nail_shapes:["杏仁甲","方圆甲"], price:"129-239", color_a:"#c95a88", color_b:"#f5c2d8", skin_brightness:5, hand_shape_fit:5, daily_convenience:3, maintenance_ease:3, style_match:5, likes:96, image_url:"assets/photos/photo_002.svg", gender_suitability:"female" },
    { id:3, title:"奶茶裸粉", category:"裸色", tags:["裸色","高级感","日常"], scene:"日常", skin_tones:["暖黄皮","小麦色"], nail_shapes:["短甲","方圆甲"], price:"89-169", color_a:"#c58f82", color_b:"#f5ded5", skin_brightness:3, hand_shape_fit:3, daily_convenience:5, maintenance_ease:5, style_match:3, likes:87, image_url:"assets/photos/photo_003.svg", gender_suitability:"all" },
    { id:4, title:"莓果镜面", category:"镜面", tags:["镜面","甜酷","显白"], scene:"聚会", skin_tones:["冷白皮","自然肤色"], nail_shapes:["长甲","杏仁甲"], price:"139-269", color_a:"#8c2758", color_b:"#f2aec7", skin_brightness:5, hand_shape_fit:4, daily_convenience:2, maintenance_ease:2, style_match:4, likes:73, image_url:"assets/photos/photo_004.svg", gender_suitability:"female" },
    { id:5, title:"珍珠蝴蝶结", category:"甜美", tags:["甜美","氛围感","约会"], scene:"约会", skin_tones:["冷白皮","自然肤色"], nail_shapes:["杏仁甲","长甲"], price:"149-289", color_a:"#f6cadc", color_b:"#ffffff", skin_brightness:4, hand_shape_fit:5, daily_convenience:2, maintenance_ease:2, style_match:5, likes:112, image_url:"assets/photos/photo_005.svg", gender_suitability:"female" },
    { id:6, title:"微醺渐变", category:"渐变", tags:["渐变","温柔","婚礼"], scene:"婚礼", skin_tones:["自然肤色","暖黄皮"], nail_shapes:["方圆甲","杏仁甲"], price:"119-219", color_a:"#e9a8bb", color_b:"#fff7f8", skin_brightness:4, hand_shape_fit:4, daily_convenience:3, maintenance_ease:3, style_match:4, likes:65, image_url:"assets/photos/photo_006.svg", gender_suitability:"female" },
    { id:7, title:"黑樱茶歇", category:"轻奢", tags:["轻奢","显手白","宴会"], scene:"宴会", skin_tones:["冷白皮","自然肤色"], nail_shapes:["长甲","方甲"], price:"159-299", color_a:"#352031", color_b:"#c490a5", skin_brightness:5, hand_shape_fit:4, daily_convenience:2, maintenance_ease:2, style_match:5, likes:54, image_url:"assets/photos/photo_007.svg", gender_suitability:"all" },
    { id:8, title:"蓝莓星闪", category:"闪钻", tags:["闪钻","清冷","节日"], scene:"节日", skin_tones:["冷白皮"], nail_shapes:["杏仁甲","长甲"], price:"169-319", color_a:"#8f9fe5", color_b:"#e9edff", skin_brightness:5, hand_shape_fit:5, daily_convenience:2, maintenance_ease:2, style_match:5, likes:91, image_url:"assets/photos/photo_008.svg", gender_suitability:"female" },
    { id:19, title:"哑光黑武士", category:"男士", tags:["男士","哑光","酷感","短甲"], scene:"日常", skin_tones:["冷白皮","自然肤色","暖黄皮","小麦色"], nail_shapes:["短甲","方圆甲","方甲"], price:"99-199", color_a:"#1a1a1a", color_b:"#3d3d3d", skin_brightness:3, hand_shape_fit:5, daily_convenience:5, maintenance_ease:5, style_match:5, likes:86, image_url:"assets/photos/photo_019.svg", gender_suitability:"male" },
    { id:20, title:"几何暗纹", category:"轻奢", tags:["男士","几何","低调","高级感"], scene:"通勤", skin_tones:["冷白皮","自然肤色","暖黄皮"], nail_shapes:["短甲","方甲","方圆甲"], price:"129-249", color_a:"#263238", color_b:"#546e7a", skin_brightness:3, hand_shape_fit:5, daily_convenience:5, maintenance_ease:4, style_match:5, likes:62, image_url:"assets/photos/photo_020.svg", gender_suitability:"male" },
    { id:23, title:"简约雾灰", category:"纯色", tags:["男士","简约","通勤","低调"], scene:"通勤", skin_tones:["冷白皮","自然肤色","暖黄皮","小麦色"], nail_shapes:["短甲","方圆甲"], price:"79-149", color_a:"#9e9e9e", color_b:"#e0e0e0", skin_brightness:2, hand_shape_fit:4, daily_convenience:5, maintenance_ease:5, style_match:4, likes:71, image_url:"assets/photos/photo_023.svg", gender_suitability:"male" },
    { id:24, title:"极简裸黑", category:"法式", tags:["男士","法式","简约","日常"], scene:"日常", skin_tones:["冷白皮","自然肤色","暖黄皮","小麦色"], nail_shapes:["短甲","方圆甲"], price:"89-169", color_a:"#2d2d2d", color_b:"#f5f5f5", skin_brightness:3, hand_shape_fit:4, daily_convenience:5, maintenance_ease:5, style_match:4, likes:58, image_url:"assets/photos/photo_025.svg", gender_suitability:"male" },
  ];
  state.posts = [
    { id:1, user_name:"小美甲控", title:"莓果猫眼终于做上了！", body:"等了2周的预约，成品太满意了。显白效果一绝。", image_data:"", likes:42, comment_count:3 },
    { id:2, user_name:"指尖上的星光", title:"婚礼渐变美甲", body:"自己设计的渐变美甲，法式+微醺粉，温柔又显气质。", image_data:"", likes:38, comment_count:7 },
    { id:3, user_name:"奶茶爱好者", title:"通勤族必备裸粉", body:"裸色系真的太适合上班族了，低调又有质感。", image_data:"", likes:25, comment_count:2 },
  ];
  state.stores = [
    { name:"花漾美甲·中心店", address:"北京市朝阳区建国路88号", rating:4.9, price_start:"¥99 起" },
    { name:"Luna Nail Studio", address:"上海市静安区南京西路1266号", rating:4.8, price_start:"¥129 起" },
    { name:"粉雾美学工作室", address:"广州市天河区体育西路111号", rating:4.7, price_start:"¥89 起" },
  ];
}
function recommendationProfileFromState() {
  const profile = state.profile || {};
  const skin = { "自然肤色": "自然黄皮", "暖黄皮": "黄白皮", "小麦色": "深肤色" };
  const hand = { "圆润型": "肉肉手", "短指型": "短粗手", "骨感型": "骨节手", "纤长型": "修长手" };
  const shape = { "圆甲": "圆形", "椭圆甲": "椭圆形", "杏仁甲": "杏仁形", "方甲": "方形", "方圆甲": "方圆形", "梯形甲": "梯形", "尖甲": "尖形" };
  const scene = { "宴会": "聚会", "夏季": "节日" };
  const length = profile.target_length || (profile.nail_shape === "短甲" ? "短" : profile.nail_shape === "长甲" ? "长" : "中");
  return {
    skin_tone: skin[profile.skin_tone] || profile.skin_tone || "自然黄皮",
    hand_shape: hand[profile.hand_shape] || profile.hand_shape || "修长手",
    nail_shape: shape[profile.nail_shape] || profile.nail_shape || "方圆形",
    scene: scene[profile.scene] || profile.scene || "日常",
    target_length: length,
    nail_conditions: Array.isArray(profile.nail_conditions) ? profile.nail_conditions : ["无明显困扰"],
    maintenance_preference: profile.maintenance_preference || "中",
    decoration_level: profile.decoration_level || { "不加饰品": "无", "细闪薄片": "轻量", "珍珠金属": "适中", "钻饰": "适中", "3D 饰品": "突出" }[profile.decoration_preference] || "轻量",
    budget_range: profile.budget_range || "不限",
    style_preference: profile.style_preference || profile.style || "",
    color_preference: profile.color_preference || "",
    safety_flag: Boolean(profile.safety_flag),
  };
}

function recommendationSelect(id, label, values, current) {
  return `<div class="field"><label for="${id}">${label}</label><select id="${id}">${values.map(value => `<option value="${value}" ${value === current ? "selected" : ""}>${value}</option>`).join("")}</select></div>`;
}

function recommendationResult(plan) {
  if (!plan) return `<div class="recommendation-empty"><span>${icon("sparkles", 22)}</span><strong>填写档案后，生成你的完整搭配方案</strong><small>会综合肤色、手型、场景、维护和预算，而非只看单个标签。</small></div>`;
  if (plan.status === "safety_hold") return `<div class="recommendation-safety"><span>${icon("shield-alert", 19)}</span><div><strong>${escapeHtml(plan.summary)}</strong><p>${escapeHtml(plan.safety_notice)}</p></div></div>`;
  const recommendation = plan.recommendation || {};
  const colors = (recommendation.colors || []).map(color => `<span class="recommendation-color"><i style="background:${escapeHtml(color.hex)}"></i>${escapeHtml(color.name)}</span>`).join("");
  const cards = (plan.items || []).map(item => {
    const style = item.style || {};
    const image = style.image_url || "";
    const priceNote = item.in_budget ? "预算内" : `约超预算 ¥${item.budget_overage || 0}`;
    return `<article class="recommendation-style"><img src="${escapeHtml(image)}" alt="${escapeHtml(style.title || "推荐款式")}" onerror="this.style.display='none'"><div><div class="recommendation-style-top"><strong>${escapeHtml(style.title || "推荐款式")}</strong><span>${item.score || 0}%</span></div><small>${escapeHtml(style.category || "") } · ¥${escapeHtml(style.price || "") } · ${priceNote}</small><p>${(item.reasons || []).slice(0, 2).map(escapeHtml).join(" ")}</p><div class="recommendation-card-actions"><button class="btn-secondary" data-recommendation-tryon="${style.id}">${icon("scan-face", 13)}试戴</button><button class="btn-primary" data-recommendation-book="${style.id}">${icon("calendar-days", 13)}预约</button></div></div></article>`;
  }).join("");
  const cautions = (plan.items || []).flatMap(item => item.cautions || []).slice(0, 2);
  return `<div class="recommendation-result"><div class="recommendation-result-head"><div><span class="eyebrow">YOUR NAIL PLAN</span><h3>你的完整搭配方案</h3><p>${escapeHtml(plan.summary || "")}</p></div><span class="recommendation-version">${escapeHtml(plan.version || "")}</span></div><div class="recommendation-summary"><div><small>推荐甲型</small><strong>${escapeHtml(recommendation.nail_shape || "")}</strong></div><div><small>建议长度</small><strong>${escapeHtml(recommendation.target_length || "")}</strong></div><div><small>表面质感</small><strong>${escapeHtml(recommendation.finish || "")}</strong></div><div><small>饰品程度</small><strong>${escapeHtml(recommendation.decoration_level || "")}</strong></div></div><section class="recommendation-section"><h4>${icon("palette", 15)}色彩方向</h4><div class="recommendation-colors">${colors}</div><p>${escapeHtml(recommendation.scene_note || "")}</p></section><section class="recommendation-section"><h4>${icon("sparkles", 15)}为你优先挑选</h4><div class="recommendation-style-list">${cards || "<p>暂时没有可推荐的款式。</p>"}</div></section><section class="recommendation-section recommendation-advice"><h4>${icon("messages-square", 15)}到店沟通建议</h4><p>${escapeHtml(plan.consultation || "")}</p></section>${cautions.length ? `<section class="recommendation-section recommendation-caution"><h4>${icon("circle-alert", 15)}提前留意</h4><ul>${cautions.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>` : ""}<section class="recommendation-section recommendation-care"><h4>${icon("heart-handshake", 15)}维护提示</h4><ul>${(plan.care || []).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul><small>${escapeHtml(plan.disclaimer || "")}</small></section></div>`;
}

adaptView = function() {
  const profile = recommendationProfileFromState();
  const conditions = ["无明显困扰", "短甲", "软薄易断", "扁平", "扇形外扩"];
  return `<section class="section recommendation-page"><div class="section-head"><div><span class="eyebrow">EXPLAINABLE NAIL MATCH</span><h2>智能适配</h2><p>从你的实际条件出发，得到可带去门店沟通的完整搭配方案。</p></div></div><div class="adapt-layout recommendation-layout"><div class="panel recommendation-form"><div class="recommendation-form-head"><h3>建立你的搭配档案</h3><span>${icon("book-open-check", 16)}资料库 v1</span></div><p class="lead">照片只用于虚拟试戴，不会被自动识别或用于判断甲况。</p><div class="upload-box recommendation-upload"><div>${icon("image-plus", 24)}</div><strong>${state.handImage ? "手部照片已载入" : "可选：添加试戴照片"}</strong><small>自然光、手背朝上更方便你在试戴页观察效果。</small><input id="hand-upload" type="file" accept="image/jpeg,image/png,image/webp" style="display:none"><button class="btn-secondary" id="choose-hand">${icon("folder-open", 14)}${state.handImage ? "更换照片" : "选择照片"}</button></div><div class="form-grid">${recommendationSelect("recommendation-skin", "肤色", ["冷白皮", "黄白皮", "自然黄皮", "深肤色"], profile.skin_tone)}${recommendationSelect("recommendation-hand", "手型", ["肉肉手", "短粗手", "骨节手", "修长手", "圆锥手", "匀称手"], profile.hand_shape)}${recommendationSelect("recommendation-shape", "想尝试的甲型", ["圆形", "椭圆形", "杏仁形", "方形", "方圆形", "梯形", "尖形"], profile.nail_shape)}${recommendationSelect("recommendation-scene", "主要场景", ["日常", "通勤", "约会", "婚礼", "聚会", "节日"], profile.scene)}${recommendationSelect("recommendation-length", "目标长度", ["短", "中", "长"], profile.target_length)}${recommendationSelect("recommendation-maintenance", "维护接受度", ["低", "中", "高"], profile.maintenance_preference)}${recommendationSelect("recommendation-decoration", "饰品接受度", ["无", "轻量", "适中", "突出"], profile.decoration_level)}${recommendationSelect("recommendation-budget", "预算范围", ["100以内", "100-160", "160-240", "240以上", "不限"], profile.budget_range)}</div><div class="recommendation-condition"><label>本甲情况 <small>最多选 3 项</small></label><div class="recommendation-chips">${conditions.map(value => `<button type="button" class="recommendation-chip ${profile.nail_conditions.includes(value) ? "selected" : ""}" data-nail-condition="${value}">${value}</button>`).join("")}</div></div><label class="recommendation-safety-check"><input id="recommendation-safety" type="checkbox" ${profile.safety_flag ? "checked" : ""}><span>我有疼痛、红肿、渗液、明显变色或破损等异常情况</span></label><button class="btn-primary recommendation-submit" id="generate-recommendation">${icon("wand-sparkles", 15)}生成完整搭配方案</button></div><div class="panel recommendation-output" id="recommendation-output">${recommendationResult(state.recommendationPlan)}</div></div></section>`;
};

function bindRecommendationActions() {
  const output = document.querySelector("#recommendation-output");
  document.querySelectorAll("[data-nail-condition]").forEach(button => button.addEventListener("click", () => {
    const selected = [...document.querySelectorAll("[data-nail-condition].selected")];
    if (!button.classList.contains("selected") && selected.length >= 3) return toast("本甲情况最多选择 3 项");
    button.classList.toggle("selected");
    if (button.dataset.nailCondition === "无明显困扰" && button.classList.contains("selected")) document.querySelectorAll("[data-nail-condition]").forEach(item => { if (item !== button) item.classList.remove("selected"); });
    if (button.dataset.nailCondition !== "无明显困扰") document.querySelector('[data-nail-condition="无明显困扰"]')?.classList.remove("selected");
  }));
  document.querySelector("#generate-recommendation")?.addEventListener("click", async () => {
    const profile = {
      skin_tone: document.querySelector("#recommendation-skin").value,
      hand_shape: document.querySelector("#recommendation-hand").value,
      nail_shape: document.querySelector("#recommendation-shape").value,
      scene: document.querySelector("#recommendation-scene").value,
      target_length: document.querySelector("#recommendation-length").value,
      maintenance_preference: document.querySelector("#recommendation-maintenance").value,
      decoration_level: document.querySelector("#recommendation-decoration").value,
      budget_range: document.querySelector("#recommendation-budget").value,
      nail_conditions: [...document.querySelectorAll("[data-nail-condition].selected")].map(item => item.dataset.nailCondition),
      safety_flag: document.querySelector("#recommendation-safety").checked,
      style_preference: state.profile.style_preference || state.profile.style || "",
      color_preference: state.profile.color_preference || "",
    };
    if (!profile.nail_conditions.length) profile.nail_conditions = ["无明显困扰"];
    try {
      const result = await api("/api/recommendations", { method: "POST", body: JSON.stringify({ profile }) });
      state.profile = { ...state.profile, ...profile };
      state.recommendationPlan = result.plan;
      if (result.user) syncUserProfile(result.user);
      output.innerHTML = recommendationResult(result.plan);
      renderIcons();
      bindRecommendationResultActions(output);
      toast(result.saved ? "搭配方案已保存到我的档案" : "搭配方案已生成，登录后可长期保存");
    } catch (error) {
      toast(error.message || "生成搭配方案失败，请稍后重试");
    }
  });
  if (output) bindRecommendationResultActions(output);
}

function bindRecommendationResultActions(container) {
  container.querySelectorAll("[data-recommendation-tryon]").forEach(button => button.addEventListener("click", () => {
    state.selectedStyle = state.styles.find(style => style.id === Number(button.dataset.recommendationTryon)) || state.selectedStyle;
    navigate("tryon");
  }));
  container.querySelectorAll("[data-recommendation-book]").forEach(button => button.addEventListener("click", () => {
    const style = state.styles.find(item => item.id === Number(button.dataset.recommendationBook));
    openBooking(style);
  }));
}

const existingMeView = meView;
meView = async function() {
  const content = await existingMeView();
  const plan = state.user?.profile?.latest_recommendation_plan || state.recommendationPlan;
  if (!state.user || !plan || plan.status !== "ready") return content;
  const top = plan.items?.[0]?.style;
  const card = `<div class="section my-recommendation"><div class="section-head"><div><h2>我的最新搭配方案</h2><p>${escapeHtml(plan.summary || "")}</p></div><button class="btn-secondary" data-view="adapt">${icon("sparkles", 14)}重新生成</button></div><div class="panel my-recommendation-card"><div><span class="eyebrow">${escapeHtml(plan.version || "")}</span><strong>${escapeHtml(top?.title || "搭配方案已保存")}</strong><small>${escapeHtml(plan.recommendation?.nail_shape || "")} · ${escapeHtml(plan.recommendation?.target_length || "")} · ${escapeHtml(plan.recommendation?.finish || "")}</small></div><button class="btn-primary" data-view="adapt">查看方案</button></div></div>`;
  return content.replace('<button class="btn-secondary" id="logout-btn"', `${card}<button class="btn-secondary" id="logout-btn"`);
};

const bindExistingViewActions = bindViewActions;
bindViewActions = function() {
  bindExistingViewActions();
  bindRecommendationActions();
};

document.addEventListener("visibilitychange", () => {
  if (document.hidden && tryonRuntime.mode === "camera") {
    stopTryonCamera("页面已暂停摄像头，点击“打开前置摄像头”可继续");
  }
});
window.addEventListener("pagehide", cleanupTryonView);
window.addEventListener("beforeunload", cleanupTryonView);

boot();
