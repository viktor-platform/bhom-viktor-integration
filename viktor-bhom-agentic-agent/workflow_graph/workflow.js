export class WorkflowGraph {
  constructor({ stage, edgesSvg, nodesHost, overlayEl }) {
    this.stage = stage;
    this.edgesSvg = edgesSvg;
    this.nodesHost = nodesHost;
    this.overlayEl = overlayEl;
    this.edgesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    this.edgesSvg.appendChild(this.edgesGroup);

    const rootStyle = getComputedStyle(document.documentElement);
    this.NODE_W = parseFloat(rootStyle.getPropertyValue("--node-w"));
    this.NODE_H = parseFloat(rootStyle.getPropertyValue("--node-h"));
    this.GAP_X  = parseFloat(rootStyle.getPropertyValue("--gap-x"));
    this.GAP_Y  = parseFloat(rootStyle.getPropertyValue("--gap-y"));
    this.EDGE_W = (rootStyle.getPropertyValue("--edge-w") || "8").trim();
    this.EDGE_CURVE = 80;

    this.canvasState = { workflow: { nodes: [] }, plan: null };
    this.data = { nodes: [] };
    this.byId = new Map();
    this.edges = [];          // {from,to}
    this.positions = new Map();// id -> {x,y}
    this.dragged = new Set();
    this.expandedTodoIds = new Set();
    this.activeId = null;

    // Zoom and pan state
    this.scale = 1;
    this.panX = 0;
    this.panY = 0;
    this.isPanning = false;
    this.panStartX = 0;
    this.panStartY = 0;
    this.panOriginX = 0;
    this.panOriginY = 0;

    this._setupPanZoom();
    this._setupResizeObserver();
  }

  _setupPanZoom() {
    // Mouse wheel zoom
    this.stage.addEventListener("wheel", (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.min(2, Math.max(0.3, this.scale * delta));

      // Zoom toward mouse position
      const rect = this.stage.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const scaleChange = newScale / this.scale;
      this.panX = mouseX - (mouseX - this.panX) * scaleChange;
      this.panY = mouseY - (mouseY - this.panY) * scaleChange;
      this.scale = newScale;

      this._applyTransform();
    }, { passive: false });

    // Pan with middle mouse or when holding space
    this.stage.addEventListener("pointerdown", (e) => {
      if (e.button === 1 || (e.button === 0 && e.target === this.stage)) {
        this.isPanning = true;
        this.panStartX = e.clientX;
        this.panStartY = e.clientY;
        this.panOriginX = this.panX;
        this.panOriginY = this.panY;
        this.stage.style.cursor = "grabbing";
        e.preventDefault();
      }
    });

    window.addEventListener("pointermove", (e) => {
      if (!this.isPanning) return;
      this.panX = this.panOriginX + (e.clientX - this.panStartX);
      this.panY = this.panOriginY + (e.clientY - this.panStartY);
      this._applyTransform();
    });

    window.addEventListener("pointerup", () => {
      if (this.isPanning) {
        this.isPanning = false;
        this.stage.style.cursor = "";
      }
    });
  }

  _setupResizeObserver() {
    if (typeof ResizeObserver === "undefined") return;
    const onResize = () => {
      this.relayout({ resetDragged: false });
      this.render();
      this.fitToView();
    };
    this._resizeObserver = new ResizeObserver(onResize);
    this._resizeObserver.observe(this.stage);
  }

  _applyTransform() {
    const cssTransform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
    this.nodesHost.style.transform = cssTransform;
    if (this.edgesGroup) {
      const svgTransform = `translate(${this.panX} ${this.panY}) scale(${this.scale})`;
      this.edgesGroup.setAttribute("transform", svgTransform);
    }
  }

  zoomIn() {
    this.scale = Math.min(2, this.scale * 1.2);
    this._applyTransform();
  }

  zoomOut() {
    this.scale = Math.max(0.3, this.scale / 1.2);
    this._applyTransform();
  }

  fitToView(zoomMultiplier = null) {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    if (nodes.length === 0) return;

    // Find bounding box of all nodes
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of nodes) {
      const pos = this.positions.get(n.id);
      if (!pos) continue;
      minX = Math.min(minX, pos.x);
      minY = Math.min(minY, pos.y);
      maxX = Math.max(maxX, pos.x + this.NODE_W);
      maxY = Math.max(maxY, pos.y + this.NODE_H);
    }

    if (minX === Infinity) return;

    const contentW = maxX - minX;
    const contentH = maxY - minY;
    const viewportPadding = this._getViewportPadding();
    const stageW = this.stage.clientWidth - viewportPadding.left - viewportPadding.right;
    const stageH = this.stage.clientHeight - viewportPadding.top - viewportPadding.bottom;
    const padding = this.EDGE_CURVE;

    if (stageW <= 0 || stageH <= 0) return;

    // Calculate scale to fit
    const scaleX = (stageW - padding * 2) / contentW;
    const scaleY = (stageH - padding * 2) / contentH;
    let calculatedScale = Math.min(scaleX, scaleY);

    // Apply zoom multiplier if provided (for initial load), otherwise cap at 100%
    if (zoomMultiplier !== null) {
      this.scale = Math.min(2, calculatedScale * zoomMultiplier);
    } else {
      this.scale = Math.min(1, calculatedScale);
    }

    // Center the content
    const scaledW = contentW * this.scale;
    const scaledH = contentH * this.scale;
    this.panX = viewportPadding.left + (stageW - scaledW) / 2 - minX * this.scale;
    this.panY = viewportPadding.top + (stageH - scaledH) / 2 - minY * this.scale;

    this._applyTransform();
  }

  resetView() {
    this.scale = 1;
    this.panX = 0;
    this.panY = 0;
    this._applyTransform();
  }

  setData(canvasState) {
    this.canvasState = canvasState && typeof canvasState === "object"
      ? canvasState
      : { workflow: { nodes: [] }, plan: null };
    this.data = this.canvasState.workflow && typeof this.canvasState.workflow === "object"
      ? this.canvasState.workflow
      : { nodes: [] };
    this._validateAndBuildGraph();
    this._renderOverlay();
  }

  _validateAndBuildGraph() {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    this.byId.clear();
    this.edges = [];

    for (const n of nodes) {
      if (!n || typeof n.id !== "string" || !n.id.trim()) {
        throw new Error("Each node must have a non-empty string id.");
      }
      if (this.byId.has(n.id)) {
        throw new Error("Duplicate node id: " + n.id);
      }
      this.byId.set(n.id, n);
    }

    for (const n of nodes) {
      const deps = Array.isArray(n.depends_on) ? n.depends_on : [];
      for (const dep of deps) {
        const depId = dep && typeof dep.node_id === "string" ? dep.node_id : null;
        if (!depId || !this.byId.has(depId)) {
          throw new Error(`Node "${n.id}" depends_on unknown node "${depId}".`);
        }
        this.edges.push({ from: depId, to: n.id });
      }
    }
  }

  topoSort() {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    const indeg = new Map();
    const out = new Map();

    for (const n of nodes) {
      indeg.set(n.id, 0);
      out.set(n.id, []);
    }
    for (const e of this.edges) {
      indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
      out.get(e.from).push(e.to);
    }

    const q = [];
    for (const [id, d] of indeg.entries()) {
      if (d === 0) q.push(id);
    }

    const order = [];
    while (q.length) {
      const id = q.shift();
      order.push(id);
      for (const nxt of out.get(id)) {
        indeg.set(nxt, indeg.get(nxt) - 1);
        if (indeg.get(nxt) === 0) q.push(nxt);
      }
    }

    if (order.length !== nodes.length) return { ok: false, order: [] };
    return { ok: true, order };
  }

  _computeDepths(order) {
    const depth = new Map();
    for (const id of order) depth.set(id, 0);

    for (const id of order) {
      const node = this.byId.get(id);
      const deps = Array.isArray(node.depends_on) ? node.depends_on : [];
      let d = 0;
      for (const dep of deps) {
        d = Math.max(d, (depth.get(dep.node_id) || 0) + 1);
      }
      depth.set(id, d);
    }
    return depth;
  }

  relayout({ resetDragged }) {
    if (resetDragged) this.dragged.clear();

    const res = this.topoSort();
    if (!res.ok) {
      return;
    }

    const order = res.order;
    const depth = this._computeDepths(order);

    const layers = new Map();
    let maxDepth = 0;
    for (const id of order) {
      const d = depth.get(id) || 0;
      maxDepth = Math.max(maxDepth, d);
      if (!layers.has(d)) layers.set(d, []);
      layers.get(d).push(id);
    }

    const w = this.stage.clientWidth;
    const viewportPadding = this._getViewportPadding();
    const topPad = viewportPadding.top;
    const leftPad = viewportPadding.left;

    if (resetDragged) this.positions.clear();

    for (let d = 0; d <= maxDepth; d++) {
      const ids = layers.get(d) || [];
      const count = ids.length;
      if (count === 0) continue;

      const totalW = (count * this.NODE_W) + ((count - 1) * this.GAP_X);
      const startX = Math.max(leftPad, (w - totalW) / 2);

      for (let i = 0; i < count; i++) {
        const id = ids[i];
        if (!resetDragged && this.dragged.has(id)) continue;
        const x = startX + i * (this.NODE_W + this.GAP_X);
        const y = topPad + d * (this.NODE_H + this.GAP_Y);
        this.positions.set(id, { x, y });
      }
    }

    this._ensurePositionsForMissing();
  }

  _ensurePositionsForMissing() {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    const missing = [];
    for (const n of nodes) {
      if (!this.positions.has(n.id)) missing.push(n.id);
    }
    if (!missing.length) return;

    const w = this.stage.clientWidth;
    const startX = 40;
    const y = 40;
    let x = startX;

    for (const id of missing) {
      if (x + this.NODE_W > w - 40) x = startX;
      this.positions.set(id, { x, y });
      x += this.NODE_W + 20;
    }
  }

  render() {
    this._renderOverlay();
    this._renderNodes();
    this._drawEdges();
  }

  _renderOverlay() {
    if (!this.overlayEl) return;

    const plan = this.canvasState.plan;
    if (!plan) {
      this.overlayEl.className = "workflow-overlay is-hidden";
      this.overlayEl.innerHTML = "";
      return;
    }

    this.overlayEl.className = "workflow-overlay";
    this.overlayEl.innerHTML = `
      ${plan ? this._renderPlanMarkup(plan) : ""}
    `;

    this._bindOverlayInteractions();
  }

  _renderPlanMarkup(plan) {
    const todos = Array.isArray(plan.todos) ? plan.todos : [];
    const total = todos.length;
    const completed = todos.filter((todo) => todo.status === "completed").length;
    const percent = total ? Math.round((completed / total) * 100) : 0;

    return `
      <div class="workflow-card-surface">
        <div class="workflow-plan-summary">
          <div class="workflow-plan-count">${escapeHtml(plan.title || "Workflow Plan")}</div>
          <div class="workflow-progress-bar" aria-hidden="true">
            <span style="width:${percent}%"></span>
          </div>
        </div>
        <div class="workflow-plan-list">
          ${todos.map((todo) => this._renderTodoMarkup(todo)).join("")}
        </div>
      </div>
    `;
  }

  _renderTodoMarkup(todo) {
    const status = todo.status || "pending";
    const isExpanded = this.expandedTodoIds.has(todo.id);
    const hasDescription = Boolean(todo.description);
    const tagName = hasDescription ? "button" : "div";
    const attrs = hasDescription
      ? `type="button" class="workflow-todo-toggle" data-todo-id="${escapeHtml(todo.id)}" aria-expanded="${isExpanded ? "true" : "false"}"`
      : `class="workflow-todo-static"`;
    return `
      <div class="workflow-todo workflow-todo-${status} ${isExpanded ? "is-expanded" : ""}">
        <${tagName} ${attrs}>
          <span class="workflow-todo-status"><span class="workflow-status-badge workflow-status-${status}"></span></span>
          <span class="workflow-todo-body">
            <span class="workflow-todo-label">${escapeHtml(todo.label || todo.id)}</span>
            ${hasDescription && isExpanded ? `<span class="workflow-todo-description">${escapeHtml(todo.description)}</span>` : ""}
          </span>
          ${hasDescription ? `<span class="workflow-todo-chevron">${isExpanded ? "⌃" : "⌄"}</span>` : ""}
        </${tagName}>
      </div>
    `;
  }

  _bindOverlayInteractions() {
    if (!this.overlayEl) return;

    for (const toggle of this.overlayEl.querySelectorAll("[data-todo-id]")) {
      toggle.addEventListener("click", () => {
        const todoId = toggle.getAttribute("data-todo-id");
        if (!todoId) return;
        if (this.expandedTodoIds.has(todoId)) {
          this.expandedTodoIds.delete(todoId);
        } else {
          this.expandedTodoIds.add(todoId);
        }
        this._renderOverlay();
      });
    }
  }

  _getViewportPadding() {
    const padding = { top: 56, right: 56, bottom: 56, left: 40 };
    if (!this.overlayEl || this.overlayEl.classList.contains("is-hidden")) {
      return padding;
    }

    const overlayWidth = this.overlayEl.offsetWidth || 0;
    if (overlayWidth > 0) {
      padding.left = overlayWidth + 48;
    }
    return padding;
  }

  _styleForNode(node) {
    return {
      bg: node.icon_bg || "#E5E5E5",
      iconClassName: node.icon ? "icon-custom" : "",
      icon: node.icon
        ? `<span class="icon-label">${escapeHtml(String(node.icon).slice(0, 3))}</span>`
        : "",
    };
  }

  _renderNodes() {
    this.nodesHost.innerHTML = "";
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];

    for (const n of nodes) {
      const pos = this.positions.get(n.id);
      if (!pos) continue;

      const style = this._styleForNode(n);

      const el = document.createElement("div");
      el.className = "node";
      el.dataset.id = n.id;
      el.style.left = pos.x + "px";
      el.style.top = pos.y + "px";
      // Create clickable icon if URL exists
      const url = n.url || "";
      const iconClass = [
        "icon",
        url ? "clickable-icon" : "",
        style.iconClassName || "",
      ]
        .filter(Boolean)
        .join(" ");

      el.innerHTML = `
        <div class="${iconClass}" style="background:${style.bg};" data-url="${escapeHtml(url)}">
          ${style.icon}
        </div>
        <div class="title" title="${escapeHtml(n.title || n.id)}">${escapeHtml(n.title || n.id)}</div>
      `;

      // Handle icon click to open URL
      const iconEl = el.querySelector(".icon");
      if (url && iconEl) {
        iconEl.addEventListener("click", (ev) => {
          ev.stopPropagation();
          window.open(url, "_blank");
        });
      }

      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this.setActive(n.id);
      });

      this._attachDrag(el, n.id);
      this.nodesHost.appendChild(el);
    }
  }

  setActive(idOrNull) {
    this.activeId = idOrNull;
    for (const el of this.nodesHost.querySelectorAll(".node")) {
      el.classList.toggle("active", idOrNull && el.dataset.id === idOrNull);
    }
  }

  _attachDrag(el, id) {
    let startX = 0, startY = 0, originX = 0, originY = 0;
    let dragging = false;

    el.addEventListener("pointerdown", (ev) => {
      // Don't start dragging if clicking on the icon
      if (ev.target.closest(".clickable-icon")) {
        return;
      }

      ev.preventDefault();
      el.setPointerCapture(ev.pointerId);
      const p = this.positions.get(id);
      if (!p) return;

      dragging = true;
      this.dragged.add(id);

      startX = ev.clientX;
      startY = ev.clientY;
      originX = p.x;
      originY = p.y;
    });

    el.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;

      const x = originX + dx;
      const y = originY + dy;
      this.positions.set(id, { x, y });
      el.style.left = x + "px";
      el.style.top = y + "px";
      this._drawEdges();
    });

    const end = (ev) => {
      if (!dragging) return;
      dragging = false;
      try { el.releasePointerCapture(ev.pointerId); } catch {}
    };

    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
  }

  _setSvgSize() {
    const w = this.stage.clientWidth;
    const h = this.stage.clientHeight;
    this.edgesSvg.style.width = "100%";
    this.edgesSvg.style.height = "100%";
    this.edgesSvg.removeAttribute("width");
    this.edgesSvg.removeAttribute("height");
    this.edgesSvg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  }

  _drawEdges() {
    this._setSvgSize();
    this.edgesGroup.innerHTML = "";

    const mk = (tag) => document.createElementNS("http://www.w3.org/2000/svg", tag);

    for (const e of this.edges) {
      const p1 = this.positions.get(e.from);
      const p2 = this.positions.get(e.to);
      if (!p1 || !p2) continue;

      const x1 = p1.x + this.NODE_W / 2;
      const y1 = p1.y + this.NODE_H;
      const x2 = p2.x + this.NODE_W / 2;
      const y2 = p2.y;

      const c1x = x1;
      const c1y = y1 + this.EDGE_CURVE;
      const c2x = x2;
      const c2y = y2 - this.EDGE_CURVE;

      const path = mk("path");
      path.setAttribute("d", `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "#111");
      path.setAttribute("stroke-width", this.EDGE_W);
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      this.edgesGroup.appendChild(path);

      const s = mk("circle");
      s.setAttribute("cx", x1);
      s.setAttribute("cy", y1);
      s.setAttribute("r", "8");
      s.setAttribute("fill", "#f7f7f7");
      s.setAttribute("stroke", "#111");
      s.setAttribute("stroke-width", "4");
      this.edgesGroup.appendChild(s);

      const t = mk("circle");
      t.setAttribute("cx", x2);
      t.setAttribute("cy", y2);
      t.setAttribute("r", "8");
      t.setAttribute("fill", "#111");
      this.edgesGroup.appendChild(t);
    }
  }

}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
