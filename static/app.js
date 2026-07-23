// ELEMENTOS DEL DOM
const authOverlay = document.getElementById('authOverlay');
const welcomeScreen = document.getElementById('welcomeScreen');
const registerForm = document.getElementById('registerForm');
const codeForm = document.getElementById('codeForm');
const pendingForm = document.getElementById('pendingForm');
const blockedForm = document.getElementById('blockedForm');

const mainApp = document.getElementById('mainApp');
const resultsList = document.getElementById('resultsList');
const searchInput = document.getElementById('searchInput');
const btnSearch = document.getElementById('btnSearch');
const loadingIndicator = document.getElementById('loadingIndicator');
const lblSectionTitle = document.getElementById('lblSectionTitle');

// REPRODUCTOR DOM
const miniPlayer = document.getElementById('miniPlayer');
const compactPlayer = document.getElementById('compactPlayer');
const expandedPlayer = document.getElementById('expandedPlayer');
const audioElement = document.getElementById('audioElement');

let deviceId = localStorage.getItem('deviceId');
let isApproved = localStorage.getItem('isApproved') === 'true';
let currentPlaylist = [];
let currentIndex = -1;

// Inicialización
window.addEventListener('DOMContentLoaded', async () => {
    if (!deviceId) {
        deviceId = 'WEB-' + Math.random().toString(36).substring(2, 12);
        localStorage.setItem('deviceId', deviceId);
    }
    
    // Registrar Service Worker para PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js').catch(err => console.log('SW no registrado', err));
    }

    // Mostrar Welcome 3 segundos
    setTimeout(() => {
        welcomeScreen.style.display = 'none';
        checkAuthStatus();
    }, 3000);
});

// AUTENTICACIÓN
async function checkAuthStatus() {
    if (isApproved) {
        unlockApp();
    }
    
    try {
        const res = await fetch(`/api/check-status?deviceId=${deviceId}`);
        const data = await res.json();
        
        switch (data.status) {
            case 'approved':
                localStorage.setItem('isApproved', 'true');
                isApproved = true;
                unlockApp();
                break;
            case 'code_sent':
                showCodeForm();
                break;
            case 'pending':
                showPendingForm();
                break;
            case 'blocked':
            case 'unregistered':
                localStorage.setItem('isApproved', 'false');
                isApproved = false;
                showForm(data.status === 'blocked' ? blockedForm : registerForm);
                if (data.status === 'unregistered' && authOverlay.style.display === 'none') {
                    alert('Acceso revocado.');
                    location.reload();
                }
                break;
        }
    } catch (e) {
        if (!isApproved) showForm(registerForm);
    }
}

function showForm(formElement) {
    authOverlay.style.display = 'flex';
    mainApp.style.display = 'none';
    [registerForm, codeForm, pendingForm, blockedForm].forEach(f => f.style.display = 'none');
    formElement.style.display = 'block';
}

function showCodeForm() { showForm(codeForm); }
function showPendingForm() { showForm(pendingForm); }
function unlockApp() {
    authOverlay.style.display = 'none';
    mainApp.style.display = 'block';
    loadHistory();
}

// BOTONES AUTH
document.getElementById('btnSendCode').addEventListener('click', async () => {
    const nombre = document.getElementById('regName').value;
    const telefono = document.getElementById('regPhone').value;
    if(!nombre || !telefono) return;
    
    try {
        const res = await fetch('/api/send-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({deviceId, nombre, telefono})
        });
        if(res.ok) showCodeForm();
        else document.getElementById('regError').style.display = 'block';
    } catch (e) { console.error(e); }
});

document.getElementById('btnVerifyCode').addEventListener('click', async () => {
    const code = document.getElementById('regPin').value;
    if(code.length !== 4) return;
    try {
        const res = await fetch('/api/verify-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({deviceId, code})
        });
        const data = await res.json();
        if(data.status === 'success' || data.user_status === 'pending') showPendingForm();
        else document.getElementById('pinError').style.display = 'block';
    } catch (e) { console.error(e); }
});

document.getElementById('btnCheckStatus').addEventListener('click', checkAuthStatus);

// BUSCADOR
btnSearch.addEventListener('click', doSearch);
searchInput.addEventListener('keyup', (e) => { if(e.key === 'Enter') doSearch(); });

async function doSearch() {
    const query = searchInput.value.trim();
    if(!query) return loadHistory();
    
    lblSectionTitle.innerText = "Buscando...";
    loadingIndicator.style.display = 'block';
    resultsList.innerHTML = '';
    
    try {
        const res = await fetch(`/buscar?termino=${encodeURIComponent(query)}`);
        const data = await res.json();
        currentPlaylist = data.canciones || [];
        renderSongs(currentPlaylist);
        lblSectionTitle.innerText = "Resultados";
    } catch(e) {
        lblSectionTitle.innerText = "Error en búsqueda";
    } finally {
        loadingIndicator.style.display = 'none';
    }
}

function loadHistory() {
    const history = JSON.parse(localStorage.getItem('history') || '[]');
    currentPlaylist = history;
    renderSongs(currentPlaylist);
    lblSectionTitle.innerText = history.length ? "Escuchadas recientemente" : "🔍 ¿Qué quieres escuchar?";
}

function saveToHistory(song) {
    let history = JSON.parse(localStorage.getItem('history') || '[]');
    history = history.filter(s => s.titulo !== song.titulo);
    history.unshift(song);
    if(history.length > 20) history.pop();
    localStorage.setItem('history', JSON.stringify(history));
}

// RENDERIZAR LISTA
function renderSongs(songs) {
    resultsList.innerHTML = '';
    songs.forEach((song, index) => {
        const div = document.createElement('div');
        div.className = 'song-item';
        div.innerHTML = `
            <img src="${song.thumbnail}" class="song-img">
            <div class="song-info">
                <div class="song-title">${song.titulo}</div>
                <div class="song-artist">${song.canal}</div>
            </div>
            <button class="song-action ${isFav(song) ? 'fav-active' : ''}">
                ${isFav(song) ? '✓' : '+'}
            </button>
        `;
        div.addEventListener('click', (e) => {
            if(e.target.tagName === 'BUTTON') toggleFav(song, e.target);
            else playSong(song, index);
        });
        resultsList.appendChild(div);
    });
}

// REPRODUCTOR
function playSong(song, index) {
    currentIndex = index;
    saveToHistory(song);
    
    document.getElementById('miniTitle').innerText = song.titulo;
    document.getElementById('miniArtist').innerText = song.canal;
    document.getElementById('miniCover').src = song.thumbnail;
    
    document.getElementById('expTitle').innerText = song.titulo;
    document.getElementById('expArtist').innerText = song.canal;
    document.getElementById('expCover').src = song.thumbnail;
    
    miniPlayer.style.display = 'block';
    
    if (song.url.includes('/descargas/')) {
        audioElement.src = song.url;
        audioElement.play();
    } else {
        lblSectionTitle.innerText = "Obteniendo audio...";
        loadingIndicator.style.display = 'block';
        fetch(`/descargar?url=${encodeURIComponent(song.url)}`)
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    audioElement.src = data.url;
                    audioElement.play();
                    currentPlaylist[index] = data; // Actualizar con URL mp3
                }
            })
            .finally(() => {
                lblSectionTitle.innerText = "Reproduciendo";
                loadingIndicator.style.display = 'none';
            });
    }
    
    updateMediaSession(song);
}

// MEDIA SESSION (Controles en pantalla de bloqueo iPhone)
function updateMediaSession(song) {
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: song.titulo,
            artist: song.canal,
            artwork: [{ src: song.thumbnail, sizes: '512x512', type: 'image/jpeg' }]
        });
        navigator.mediaSession.setActionHandler('play', () => audioElement.play());
        navigator.mediaSession.setActionHandler('pause', () => audioElement.pause());
        navigator.mediaSession.setActionHandler('previoustrack', playPrev);
        navigator.mediaSession.setActionHandler('nexttrack', playNext);
    }
}

function playNext() {
    if(currentIndex < currentPlaylist.length - 1) {
        playSong(currentPlaylist[currentIndex + 1], currentIndex + 1);
    } else {
        // Modo Radio
        const q = currentPlaylist[currentIndex]?.canal || '';
        if(q) {
            fetch(`/buscar?termino=${encodeURIComponent(q)}`)
            .then(res => res.json())
            .then(data => {
                if(data.canciones && data.canciones.length > 0) {
                    currentPlaylist = data.canciones;
                    playSong(currentPlaylist[0], 0);
                }
            });
        }
    }
}

function playPrev() {
    if(audioElement.currentTime > 3 || currentIndex === 0) {
        audioElement.currentTime = 0;
    } else {
        playSong(currentPlaylist[currentIndex - 1], currentIndex - 1);
    }
}

// EVENTOS AUDIO
audioElement.addEventListener('play', () => {
    document.getElementById('btnPlayMini').innerText = '⏸';
    document.getElementById('btnPlayExp').innerText = '⏸';
});
audioElement.addEventListener('pause', () => {
    document.getElementById('btnPlayMini').innerText = '▶';
    document.getElementById('btnPlayExp').innerText = '▶';
});
audioElement.addEventListener('ended', playNext);

audioElement.addEventListener('timeupdate', () => {
    const current = audioElement.currentTime;
    const duration = audioElement.duration || 1;
    document.getElementById('progressBar').value = (current / duration) * 100;
    document.getElementById('currentTime').innerText = formatTime(current);
    document.getElementById('totalTime').innerText = formatTime(duration);
});

document.getElementById('progressBar').addEventListener('input', (e) => {
    const duration = audioElement.duration || 1;
    audioElement.currentTime = (e.target.value / 100) * duration;
});

function formatTime(sec) {
    if (isNaN(sec)) return "00:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
}

// CONTROLES UI
document.getElementById('btnPlayMini').addEventListener('click', (e) => {
    e.stopPropagation();
    audioElement.paused ? audioElement.play() : audioElement.pause();
});
document.getElementById('btnPlayExp').addEventListener('click', () => {
    audioElement.paused ? audioElement.play() : audioElement.pause();
});
document.getElementById('btnNextExp').addEventListener('click', playNext);
document.getElementById('btnPrevExp').addEventListener('click', playPrev);

compactPlayer.addEventListener('click', () => {
    expandedPlayer.style.display = 'flex';
});
document.getElementById('btnCollapse').addEventListener('click', () => {
    expandedPlayer.style.display = 'none';
});

// FAVORITOS
function isFav(song) {
    const favs = JSON.parse(localStorage.getItem('favs') || '[]');
    return favs.some(s => s.titulo === song.titulo);
}

function toggleFav(song, btnElement) {
    let favs = JSON.parse(localStorage.getItem('favs') || '[]');
    if(isFav(song)) {
        favs = favs.filter(s => s.titulo !== song.titulo);
        btnElement.classList.remove('fav-active');
        btnElement.innerHTML = '+';
    } else {
        favs.unshift(song);
        btnElement.classList.add('fav-active');
        btnElement.innerHTML = '✓';
    }
    localStorage.setItem('favs', JSON.stringify(favs));
    
    // Si estamos en la pestaña de favoritos, recargar
    if(document.getElementById('tabFavs').classList.contains('active')) {
        renderSongs(favs);
    }
}

// PESTAÑAS
document.getElementById('tabNube').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('tabFavs').classList.remove('active');
    loadHistory();
});

document.getElementById('tabFavs').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('tabNube').classList.remove('active');
    const favs = JSON.parse(localStorage.getItem('favs') || '[]');
    currentPlaylist = favs;
    renderSongs(favs);
    lblSectionTitle.innerText = `⭐ Mis Canciones Favoritas (${favs.length})`;
});
