const fmt = value => value ? new Date(value).toLocaleString('pt-PT') : '—';
const speed = value => value == null ? '—' : `${value} B/s`;
const bytes = value => {
  if (value == null) return '—';
  const units = ['B','KB','MB','GB','TB','PB'];
  let n = Number(value);
  let i = 0;
  while (Math.abs(n) >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
};

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function refresh() {
  try {
    const [health, stats, devices, sessions] = await Promise.all([
      getJson('/api/v1/health'), getJson('/api/v1/stats'), getJson('/api/v1/devices'), getJson('/api/v1/sessions?limit=10')
    ]);
    document.querySelector('#collector-status').textContent = health.last_collection_error
      ? `Erro: ${health.last_collection_error}`
      : health.last_traffic_collection_error
        ? `Collector: ${health.collector_interval}s · tráfego: ${health.last_traffic_collection_error}`
        : `Collector: ${health.collector_interval}s · última ${fmt(health.last_collection)} · tráfego ${health.last_traffic_count}`;
    document.querySelector('#stat-devices').textContent = stats.devices;
    document.querySelector('#stat-online').textContent = stats.online;
    document.querySelector('#stat-offline').textContent = stats.offline;
    document.querySelector('#stat-observations').textContent = stats.observations;
    document.querySelector('#devices').innerHTML = devices.map(d => `
      <tr class="device-row" onclick="openDevice('${encodeURIComponent(d.mac)}')" title="Abrir detalhes"><td class="${d.online ? 'online':'offline'}"><span class="dot"></span>${d.online ? 'Online':'Offline'}</td>
      <td><strong>${escapeHtml(d.name || 'Sem nome')}</strong></td><td>${escapeHtml(d.ip || '—')}</td><td>${escapeHtml(d.mac)}</td>
      <td>${escapeHtml(d.connection_type || '—')}</td><td>${speed(d.download_speed)}</td><td>${speed(d.upload_speed)}</td><td>${fmt(d.last_seen)}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">Sem dispositivos.</td></tr>';
    document.querySelector('#sessions').innerHTML = sessions.map(s => `<tr><td><strong>${escapeHtml(s.device_name || 'Sem nome')}</strong><br><small>${escapeHtml(s.mac)}</small></td><td>${fmt(s.started_at)}</td><td>${fmt(s.ended_at)}</td><td class="${s.ended_at ? 'offline':'online'}">${s.ended_at ? 'Terminada':'Em curso'}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">Sem sessões.</td></tr>';
  } catch (error) {
    document.querySelector('#collector-status').textContent = `Erro: ${error.message}`;
  }
}

async function collectNow() {
  document.querySelector('#collector-status').textContent = 'A recolher…';
  try { await getJson('/api/v1/collector/run', {method:'POST'}); await refresh(); }
  catch (error) { document.querySelector('#collector-status').textContent = `Erro: ${error.message}`; }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

refresh();
setInterval(refresh, 10000);


async function openDevice(encodedMac) {
  const mac = decodeURIComponent(encodedMac);
  try {
    const device = await getJson(`/api/v1/devices/${encodeURIComponent(mac)}/history?limit=200`);
    document.querySelector('#device-detail').hidden = false;
    document.querySelector('#detail-name').textContent = device.name || 'Dispositivo sem nome';
    document.querySelector('#detail-status').innerHTML = `<span class="${device.online ? 'online' : 'offline'}"><span class="dot"></span>${device.online ? 'Online' : 'Offline'}</span>`;
    document.querySelector('#detail-ip').textContent = device.ip || '—';
    document.querySelector('#detail-mac').textContent = device.mac || '—';
    document.querySelector('#detail-history').innerHTML = (device.history || []).map(item => `
      <tr>
        <td>${fmt(item.started_at)}</td>
        <td>${fmt(item.ended_at)}</td>
        <td>${bytes(item.traffic?.download_bytes)}</td>
        <td>${bytes(item.traffic?.upload_bytes)}</td>
        <td><strong>${bytes(item.traffic?.total_bytes)}</strong></td>
      </tr>`).join('') || '<tr><td colspan="5" class="empty">Sem histórico de ligações.</td></tr>';
    document.querySelector('#device-detail').scrollIntoView({behavior:'smooth', block:'start'});
  } catch (error) {
    document.querySelector('#collector-status').textContent = `Erro: ${error.message}`;
  }
}

function closeDevice() {
  document.querySelector('#device-detail').hidden = true;
}
