class PolygonEditor {
  constructor(canvasId, videoId) {
    this.canvas = document.getElementById(canvasId);
    this.video = document.getElementById(videoId);
    this.ctx = this.canvas.getContext('2d');
    this.areas = [];
    this.activeArea = null;
    this.draggingPoint = null;
    this.isEditing = false;

    this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
    this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
    this.canvas.addEventListener('mouseup', this.handleMouseUp.bind(this));

    this.setupCanvasResize();
  }

  setupCanvasResize() {
    const checkInterval = setInterval(() => {
      if (this.video.naturalWidth > 0 && this.video.naturalHeight > 0) {
        clearInterval(checkInterval);
        this.resizeCanvas();
        this.loadPolygonFromBackend();
      }
    }, 100);

    window.addEventListener('resize', () => this.resizeCanvas());
  }

  resizeCanvas() {
    const rect = this.video.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';

    this.areas.forEach(area => {
      if (area.coordinates && area.coordinates.length >= 3) {
        this.loadPointsForArea(area);
      }
    });

    this.draw();
  }

  async loadPolygonFromBackend() {
    try {
      const response = await fetch(`http://localhost:8000/api/config/areas?ts=${Date.now()}`, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" }
        });
      if (!response.ok) throw new Error('No polygons found');

      const data = await response.json();
      console.log('Loaded areas from backend:', data);

      const colors = ['#00ff00', '#ff00ff', '#00ffff', '#ffff00', '#ff8800'];
      this.areas = data.map((area, idx) => ({
        name: area.area_name,
        points: [],
        coordinates: area.coordinates,
        color: colors[idx % colors.length],
        description: area.description || ''
      }));

      this.areas.forEach(area => {
        if (area.coordinates && area.coordinates.length >= 3) {
          this.loadPointsForArea(area);
        }
      });

      document.dispatchEvent(new CustomEvent('polygon-updated', {
        detail: { areas: this.areas }
      }));

      this.draw();
    } catch (error) {
      console.warn('Using default polygon', error);
      this.areas = [{
        name: 'high_risk_area_1',
        coordinates: [[300,200],[900,200],[900,500],[300,500]],
        points: [],
        color: '#00ff00'
      }];
      this.areas.forEach(area => this.loadPointsForArea(area));
      this.draw();
    }
  }

  loadPointsForArea(area) {
    if (!this.video.naturalWidth || !this.canvas.width) {
      setTimeout(() => this.loadPointsForArea(area), 200);
      return;
    }

    const scaleX = this.canvas.width / this.video.naturalWidth;
    const scaleY = this.canvas.height / this.video.naturalHeight;

    area.points = area.coordinates.map(([x, y]) => ({ x: x * scaleX, y: y * scaleY }));
  }

  startEditing(areaName = null) {
    if (!areaName && this.areas.length > 0) {
      this.activeArea = this.areas[0];
    } else {
      this.activeArea = this.areas.find(a => a.name === areaName);
    }

    if (!this.activeArea) {
      alert('Area not found!');
      return;
    }

    console.log('Editing area:', this.activeArea.name);
    this.isEditing = true;
    this.canvas.classList.add('editable');
    this.draw();
  }

  stopEditing() {
    this.isEditing = false;
    this.canvas.classList.remove('editable');
    this.draggingPoint = null;
    this.activeArea = null;
    this.draw();
  }

  handleMouseDown(e) {
    if (!this.isEditing || !this.activeArea) return;

    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const points = this.activeArea.points;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      const dist = Math.hypot(p.x - x, p.y - y);
      if (dist < 10) {
        this.draggingPoint = i;
        return;
      }
    }
  }

  handleMouseMove(e) {
    if (!this.isEditing || this.draggingPoint === null || !this.activeArea) return;

    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    this.activeArea.points[this.draggingPoint] = { x, y };
    this.draw();
  }

  handleMouseUp() {
    this.draggingPoint = null;
  }

  draw() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    this.areas.forEach(area => {
      if (area.points.length < 2) return;

      const isActive = this.isEditing && this.activeArea === area;

      this.ctx.beginPath();
      this.ctx.moveTo(area.points[0].x, area.points[0].y);
      area.points.slice(1).forEach(p => this.ctx.lineTo(p.x, p.y));
      this.ctx.closePath();

      this.ctx.fillStyle = isActive ? `${area.color}33` : `${area.color}1A`;
      this.ctx.fill();
      this.ctx.strokeStyle = area.color;
      this.ctx.lineWidth = isActive ? 3 : 2;
      this.ctx.stroke();

      if (area.points.length > 0) {
        const labelX = area.points[0].x;
        const labelY = area.points[0].y - 10;

        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        this.ctx.fillRect(labelX - 5, labelY - 15, area.name.length * 7 + 10, 20);

        this.ctx.fillStyle = area.color;
        this.ctx.font = 'bold 12px Inter';
        this.ctx.fillText(area.name, labelX, labelY);
      }

      if (isActive) {
        area.points.forEach((p, i) => {
          this.ctx.beginPath();
          this.ctx.arc(p.x, p.y, 8, 0, 2 * Math.PI);
          this.ctx.fillStyle = i === this.draggingPoint ? '#ff0000' : '#00ffff';
          this.ctx.fill();
          this.ctx.strokeStyle = '#fff';
          this.ctx.lineWidth = 2;
          this.ctx.stroke();
          this.ctx.fillStyle = '#000';
          this.ctx.font = 'bold 11px Inter';
          this.ctx.fillText(i + 1, p.x - 3, p.y + 4);
        });
      }
    });
  }

  async savePolygon() {
    if (!this.activeArea) {
      alert('No area selected for editing');
      return false;
    }

    if (this.activeArea.points.length < 3) {
      alert('Need at least 3 points');
      return false;
    }

    const scaleX = this.video.naturalWidth / this.canvas.width;
    const scaleY = this.video.naturalHeight / this.canvas.height;

    const videoPoints = this.activeArea.points.map(p => [
      Math.round(p.x * scaleX),
      Math.round(p.y * scaleY)
    ]);

    try {
      console.log('Saving polygon:', this.activeArea.name, videoPoints);

      const response = await fetch(`http://localhost:8000/api/config/area/${this.activeArea.name}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coordinates: videoPoints,
          description: this.activeArea.description || 'Monitoring area'
        })
      });

      if (!response.ok) throw new Error('Save failed');

      try {
        await fetch(`http://localhost:8000/api/config/area/${this.activeArea.name}/reset`, { method: 'POST' });
      } catch (resetErr) {
        console.warn('Failed to clear old data:', resetErr);
      }

      this.activeArea.coordinates = videoPoints;

      alert(`Polygon "${this.activeArea.name}" saved successfully!`);

      document.dispatchEvent(new CustomEvent('polygon-updated', { detail: { areas: this.areas } }));

      return true;
    } catch (err) {
      console.error('Save error', err);
      alert('Failed to save: ' + err.message);
      return false;
    }
  }

  getAreas() {
    return this.areas;
  }

  // replace old loadPoints call
  loadPoints(coordinates, name = 'loaded_area') {
    if (!coordinates || coordinates.length < 3) return;

    const scaleX = this.canvas.width / this.video.naturalWidth;
    const scaleY = this.canvas.height / this.video.naturalHeight;

    const points = coordinates.map(([x, y]) => ({ x: x * scaleX, y: y * scaleY }));

    this.areas = [{
      name: name,
      coordinates: coordinates,
      points: points,
      color: '#00ff00'
    }];

    this.draw();
  }
}

// Init
let polygonEditor;
document.addEventListener('DOMContentLoaded', () => {
  polygonEditor = new PolygonEditor('polygon-canvas', 'live-video');

  document.getElementById('btn-edit-polygon').addEventListener('click', () => {
    polygonEditor.startEditing();
    document.getElementById('btn-edit-polygon').style.display = 'none';
    document.getElementById('btn-save-polygon').style.display = 'inline-block';
    document.getElementById('btn-cancel-polygon').style.display = 'inline-block';
  });

  document.getElementById('btn-save-polygon').addEventListener('click', async () => {
    const success = await polygonEditor.savePolygon();
    if (success) {
      polygonEditor.stopEditing();
      document.getElementById('btn-edit-polygon').style.display = 'inline-block';
      document.getElementById('btn-save-polygon').style.display = 'none';
      document.getElementById('btn-cancel-polygon').style.display = 'none';
    }
  });

  document.getElementById('btn-cancel-polygon').addEventListener('click', () => {
    polygonEditor.loadPolygonFromBackend();
    polygonEditor.stopEditing();
    document.getElementById('btn-edit-polygon').style.display = 'inline-block';
    document.getElementById('btn-save-polygon').style.display = 'none';
    document.getElementById('btn-cancel-polygon').style.display = 'none';
  });

  document.getElementById('btn-reset-polygon').addEventListener('click', async () => {
    if (!confirm('Reset polygon to default? This will reload from backend.')) return;
    await polygonEditor.loadPolygonFromBackend();
  });
});
