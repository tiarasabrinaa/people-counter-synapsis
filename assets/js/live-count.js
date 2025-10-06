// live-count.js - Multi-Area Detection Rendering
let currentAreas = [];

// Listener polygon update
document.addEventListener('polygon-updated', (e) => {
  if (e.detail.areas) {
    currentAreas = e.detail.areas;
    console.log('✅ Polygon updated in live-count, areas:', currentAreas.length);
  }
  fetchLiveDetections();
});

async function fetchLiveDetections() {
  try {
    const response = await fetch('http://localhost:8000/api/stats/live');
    if (!response.ok) throw new Error('Fetch failed');

    const data = await response.json();
    renderDetections(data);
  } catch (err) {
    console.error('Error fetching detections:', err);
    renderDetections([]);
  }
}

function renderDetections(detections) {
  const canvas = document.getElementById('polygon-canvas');
  const video = document.getElementById('live-video');
  const ctx = canvas.getContext('2d');

  if (!canvas.width || !canvas.height) return;

  // 1. Clear canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 2. Redraw all polygons first
  if (typeof polygonEditor !== 'undefined' && polygonEditor.areas.length > 0) {
    polygonEditor.areas.forEach(area => {
      if (area.points.length < 2) return;

      const isActive = polygonEditor.isEditing && polygonEditor.activeArea === area;

      ctx.beginPath();
      ctx.moveTo(area.points[0].x, area.points[0].y);
      area.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.closePath();

      ctx.fillStyle = isActive ? `${area.color}33` : `${area.color}1A`;
      ctx.fill();
      ctx.strokeStyle = area.color;
      ctx.lineWidth = isActive ? 3 : 2;
      ctx.stroke();

      if (area.points.length > 0) {
        const labelX = area.points[0].x;
        const labelY = area.points[0].y - 10;
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(labelX - 5, labelY - 15, area.name.length * 7 + 10, 20);
        
        ctx.fillStyle = area.color;
        ctx.font = 'bold 12px Inter';
        ctx.fillText(area.name, labelX, labelY);
      }

      if (isActive) {
        area.points.forEach((p, i) => {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 8, 0, 2 * Math.PI);
          ctx.fillStyle = i === polygonEditor.draggingPoint ? '#ff0000' : '#00ffff';
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.fillStyle = '#000';
          ctx.font = 'bold 11px Inter';
          ctx.fillText(i + 1, p.x - 3, p.y + 4);
        });
      }
    });
  }

  // 3. Draw bounding boxes
  if (!detections || !Array.isArray(detections) || detections.length === 0) {
    updateBboxInfo(0, 0, 0);
    return;
  }

  // Sync currentAreas with polygonEditor if empty
  if (currentAreas.length === 0 && typeof polygonEditor !== 'undefined') {
    currentAreas = polygonEditor.areas;
  }

  const scaleX = canvas.width / (video.naturalWidth || 1920);
  const scaleY = canvas.height / (video.naturalHeight || 1080);

  let insideCount = 0;
  let outsideCount = 0;

  detections.forEach(obj => {
    const x = obj.x * scaleX;
    const y = obj.y * scaleY;
    const w = obj.width * scaleX;
    const h = obj.height * scaleY;
    const centerX = obj.center_x * scaleX;
    const centerY = obj.center_y * scaleY;

    // RECALCULATE inside/outside dengan polygon TERBARU (ignore backend data)
    let isInside = false;
    let containingArea = null;

    currentAreas.forEach(area => {
      if (area.points && area.points.length >= 3) {
        if (pointInPolygon({ x: centerX, y: centerY }, area.points)) {
          isInside = true;
          containingArea = area;
        }
      }
    });

    if (isInside) insideCount++;
    else outsideCount++;

    // Draw bbox dengan warna berdasarkan HASIL CALCULATE (bukan backend)
    ctx.strokeStyle = isInside ? '#FF0000' : '#0000FF';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);

    ctx.beginPath();
    ctx.arc(centerX, centerY, 4, 0, 2 * Math.PI);
    ctx.fillStyle = isInside ? '#FF0000' : '#0000FF';
    ctx.fill();

    const labelText = containingArea 
      ? `#${obj.track_id} (${containingArea.name})` 
      : `#${obj.track_id}`;
    
    ctx.fillStyle = isInside ? '#FF0000' : '#0000FF';
    ctx.font = 'bold 12px Inter';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 3;
    ctx.strokeText(labelText, x, y - 5);
    ctx.fillText(labelText, x, y - 5);
  });

  updateBboxInfo(detections.length, insideCount, outsideCount);
}

function updateBboxInfo(total, inside, outside) {
  const bboxCount = document.getElementById('bbox-count');
  if (bboxCount) {
    bboxCount.innerHTML = `Detected: ${total} objects<br>Inside: ${inside} | Outside: ${outside}`;
  }
}

function pointInPolygon(point, points) {
  if (!points || points.length < 3) return false;
  
  let x = point.x, y = point.y;
  let inside = false;
  
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    let xi = points[i].x, yi = points[i].y;
    let xj = points[j].x, yj = points[j].y;
    
    let intersect = ((yi > y) !== (yj > y)) && 
                    (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  
  return inside;
}

setInterval(fetchLiveDetections, 2000);
setTimeout(fetchLiveDetections, 1000);