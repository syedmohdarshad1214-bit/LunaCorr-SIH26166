(() => {
  const overlay = document.getElementById("startupOverlay");
  const frame = document.getElementById("startupFrame");
  const app = document.querySelector(".app");
  let appReady = false, sceneReady = false, closed = false;
  app.inert = true;
  const timeout = setTimeout(close, 20000);
  function close() {
    if (closed) return;
    closed = true;
    clearTimeout(timeout);
    app.inert = false;
    overlay.classList.add("leaving");
    setTimeout(() => { frame.src = "about:blank"; overlay.remove(); }, 850);
  }
  function finish() {
    if (appReady && sceneReady && !closed)
      frame.contentWindow.postMessage({type:"lunacorr:finish-loader"}, location.origin);
  }
  addEventListener("lunacorr:explorer-ready", () => { appReady = true; finish(); }, {once:true});
  addEventListener("lunacorr:explorer-error", close, {once:true});
  addEventListener("message", event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type === "lunacorr:loader-ready") { sceneReady = true; finish(); }
    if (["lunacorr:loader-done", "lunacorr:loader-error"].includes(event.data?.type)) close();
  });
  document.getElementById("skipStartup").onclick = close;
  frame.src = "/static/startup-loader.html?v=1";
})();
