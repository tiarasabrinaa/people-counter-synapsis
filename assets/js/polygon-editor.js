// assets/js/polygon-editor.js
// Polygon editor for creating and updating a polygon on the canvas overlay.

class PolygonEditor {
  constructor(canvasId = 'polygon-canvas', videoId = 'live-video') {
    this.canvas = document.getElementById(canvasId);
    this.video = document.getElementById(videoId);
    if (!this.canvas || !this.video) return;

    this.ctx = this.canvas.getContext('2d');
    this.points = [];
    this.dragIndex = -1;
    this.isEditing = false;

    // Style settings
    this.strokeColor = '#00ff00';
    this.fillColor = 'rgba(0,255,0,0.15)';
    this.pointColor = '#ffffff';
    this.pointBorder = '#00ff00';
    this.pointRadius = 7;

    // Event bindings
    this._onMouseDown = this._onMouseDown.bind(this);
    this._onMouseMove = this._onMouseMove.bind(this);
    this._onMouseUp = this._onMouseUp.bind(this);
    this._onResize = this._onResize.bind(this);

    this._initCanvasResize();
    this._loadPolygon();
  }

  // --- Canvas Resize ---
  _initCanvasResize() {
    const syncCanvas = () => {
      const rect = this.video.getBoundingClientRect();
      this.canvas.width = rect.width;
      this.canvas.height = rect.height;
      this.canvas.style.width = rect.width + 'px';
      this.canvas.style.height = rect.height + 'px';
      this.draw();
    };

    this.video.addEventListener('loadeddata', syncCanvas);
    window.addEventListener('resize', syncCanvas);
    setTimeout(syncCanvas, 1000);
  }

  // --- Load polygon from backend ---
  async _loadPolygon() {
    try {
      const res = await fetch('http://localhost:8000/api/config/areas');
      const data = await res.json();
      if (Array.isArray(data) && data[0]?.coordinates?.length >= 3) {
        this.loadPoints(data[0].coordinates);
        console.log('✅ Polygon loaded from backend:', data[0].coordinates);
      } else {
        throw new Error('No polygon found');
      }
    } catch (err) {
      console.warn('⚠️ Using default polygon fallback');
      this.points = [
        [200, 200],
        [800, 200],
        [800, 500],
        [200, 500],
      ];
      this.draw();
    }
  }

  // --- Save Polygon to backend ---
  async _savePolygon() {
    if (this.points.length < 3) {
      alert('Minimal 3 titik diperlukan!');
      return;
    }

    const scaleX = this.video.naturalWidth / this.canvas.width;
    const scaleY = this.video.naturalHeight / this.canvas.height;
    const videoPoints = this.points.map(([x, y]) => [
      Math.round(x * scaleX),
      Math.round(y * scaleY),
    ]);

    try {
      const res = await fetch('http://localhost:8000/api/config/area', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          area_name: 'high_risk_area_1',
          coordinates: videoPoints,
        }),
      });
      if (!res.ok) throw new Error('Failed to save polygon');
      alert('✅ Polygon saved successfully!');
    } catch (err) {
      console.error('Save error:', err);
      alert('❌ Gagal menyimpan polygon');
    }
  }

  // --- Points & Drawing ---
  loadPoints(coords) {
    const scaleX = this.canvas.width / this.video.naturalWidth;
    const scaleY = this.canvas.height / this.video.naturalHeight;
    this.points = coords.map(([x, y]) => [x * scaleX, y * scaleY]);
    this.draw();
  }

  draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    if (this.points.length >= 3) {
      ctx.beginPath();
      this.points.forEach(([x, y], i) => {
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.fillStyle = this.fillColor;
      ctx.fill();
      ctx.lineWidth = 3;
      ctx.strokeStyle = this.strokeColor;
      ctx.stroke();
    }

    this.points.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, this.pointRadius, 0, 2 * Math.PI);
      ctx.fillStyle = this.pointColor;
      ctx.fill();
      ctx.strokeStyle = this.pointBorder;
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  }

  _getMousePos(e) {
    const rect = this.canvas.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  _hitPoint(x, y) {
    for (let i = 0; i < this.points.length; i++) {
      const [px, py] = this.points[i];
      const dist = Math.hypot(px - x, py - y);
      if (dist < 12) return i;
    }
    return -1;
  }

  // --- Mouse Handlers ---
  _onMouseDown(e) {
    if (!this.isEditing) return;
    const [x, y] = this._getMousePos(e);
    const idx = this._hitPoint(x, y);
    if (idx >= 0) {
      this.dragIndex = idx;
    }
  }

  _onMouseMove(e) {
    if (!this.isEditing || this.dragIndex === -1) return;
    const [x, y] = this._getMousePos(e);
    this.points[this.dragIndex] = [x, y];
    this.draw();
  }

  _onMouseUp() {
    this.dragIndex = -1;
  }

  // --- Control ---
  enableEdit() {
    if (this.isEditing) return;
    this.isEditing = true;
    this.canvas.classList.add('editable');
    this.canvas.addEventListener('mousedown', this._onMouseDown);
    this.canvas.addEventListener('mousemove', this._onMouseMove);
    this.canvas.addEventListener('mouseup', this._onMouseUp);
  }

  disableEdit() {
    this.isEditing = false;
    this.canvas.classList.remove('editable');
    this.canvas.removeEventListener('mousedown', this._onMouseDown);
    this.canvas.removeEventListener('mousemove', this._onMouseMove);
    this.canvas.removeEventListener('mouseup', this._onMouseUp);
    this.draw();
  }
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
  const editor = new PolygonEditor();

  const btnEdit = document.getElementById('btn-edit-polygon');
  const btnSave = document.getElementById('btn-save-polygon');
  const btnCancel = document.getElementById('btn-cancel-polygon');

  if (btnEdit) {
    btnEdit.onclick = () => {
      editor.enableEdit();
      btnEdit.style.display = 'none';
      btnSave.style.display = 'inline-block';
      btnCancel.style.display = 'inline-block';
    };
  }

  if (btnCancel) {
    btnCancel.onclick = () => {
      editor.disableEdit();
      btnEdit.style.display = 'inline-block';
      btnSave.style.display = 'none';
      btnCancel.style.display = 'none';
    };
  }

  if (btnSave) {
    btnSave.onclick = async () => {
      await editor._savePolygon();
      editor.disableEdit();
      btnEdit.style.display = 'inline-block';
      btnSave.style.display = 'none';
      btnCancel.style.display = 'none';
    };
  }
});
