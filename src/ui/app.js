/**
 * mefresh Frontend Application Controller
 * Connects QWebChannel to UI, orchestrates audio, telemetry, package priming,
 * silent deployment, and Windows debloating.
 */

class MeFreshApp {
    constructor() {
        this.bridge = null;
        this.primedPackages = [];
        this.deploymentQueue = [];
        this.debloatCatalog = { appx: [], telemetry: [], system: [], services: [] };
        this.currentEditIndex = -1;
        this.deployTimerInterval = null;
        this.deployStartTime = 0;

        this.cpuHistory = new Array(20).fill(0);
        this.ramHistory = new Array(20).fill(0);
        this.isTelemetryVisible = true;
        this.init();
    }

    init() {
        // Initialize Background Canvas
        new CyberBackground('bg-canvas');

        // Setup QWebChannel Bridge
        this.initWebChannel();

        // Bind DOM Event Listeners
        this.bindEvents();

        // Play subtle boot sound on first interaction
        document.body.addEventListener('click', () => {
            cyberAudio.init();
        }, { once: true });
    }

    initWebChannel() {
        const tryConnect = () => {
            if (typeof QWebChannel !== "undefined" && window.qt && window.qt.webChannelTransport) {
                new QWebChannel(window.qt.webChannelTransport, (channel) => {
                    this.bridge = channel.objects.pyBridge;
                    this.setupBridgeSignals();
                    this.logTerminal("INFO", "[SYSTEM] Connected to mefresh Python Core Engine.");
                    this.loadInitialData();
                });
                return true;
            }
            return false;
        };

        if (!tryConnect()) {
            let attempts = 0;
            const timer = setInterval(() => {
                attempts++;
                if (tryConnect() || attempts > 60) {
                    clearInterval(timer);
                    if (attempts > 60 && !this.bridge) {
                        console.warn("QWebChannel not detected. Running in mock/standalone mode.");
                        this.logTerminal("WARNING", "[SYSTEM] Standalone Web Mode. Native Windows hooks simulated.");
                        this.loadMockData();
                    }
                }
            }, 50);
        }
    }

    setupBridgeSignals() {
        if (!this.bridge) return;

        // Telemetry Update Signal
        this.bridge.telemetrySignal.connect((jsonStr) => {
            try {
                const data = JSON.parse(jsonStr);
                this.updateTelemetryHUD(data);
            } catch (e) {
                console.error("Telemetry parse error", e);
            }
        });

        // Package Search Results Signal
        this.bridge.searchResultSignal.connect((jsonStr) => {
            try {
                const results = JSON.parse(jsonStr);
                this.renderSearchResults(results);
            } catch (e) {
                console.error("Search parse error", e);
            }
        });

        // Download Progress Signal
        this.bridge.downloadProgressSignal.connect((jsonStr) => {
            try {
                const data = JSON.parse(jsonStr);
                this.handleDownloadProgress(data);
            } catch (e) {
                console.error("Download progress parse error", e);
            }
        });

        // Bundle Creation Progress Signal
        this.bridge.bundleProgressSignal.connect((jsonStr) => {
            try {
                const data = JSON.parse(jsonStr);
                this.handleBundleProgress(data);
            } catch (e) {
                console.error("Bundle progress parse error", e);
            }
        });

        // Silent Installer Engine Event Signal
        this.bridge.installerEventSignal.connect((evtType, jsonStr) => {
            try {
                const data = JSON.parse(jsonStr);
                this.handleInstallerEvent(evtType, data);
            } catch (e) {
                console.error("Installer event error", e);
            }
        });

        // Debloat Log & Progress Signal
        this.bridge.debloatLogSignal.connect((lvl, msg) => {
            this.logTerminal(lvl, `[DEBLOAT] ${msg}`);
        });

        this.bridge.debloatProgressSignal.connect((done, total) => {
            const pct = Math.round((done / Math.max(total, 1)) * 100);
            const pBar = document.getElementById('debloat-progress-bar');
            if (pBar) pBar.style.width = `${pct}%`;
        });

        // Restore Point Result Signal
        this.bridge.restorePointResultSignal.connect((jsonStr) => {
            try {
                const res = JSON.parse(jsonStr);
                if (res.success) {
                    cyberAudio.itemSuccess();
                    this.logTerminal("SUCCESS", `[SAFETY SHIELD] ${res.message}`);
                    alert(res.message);
                } else {
                    cyberAudio.warning();
                    this.logTerminal("ERROR", `[SAFETY SHIELD] ${res.message}`);
                    alert(res.message);
                }
            } catch (e) {}
        });
    }

    loadInitialData() {
        if (!this.bridge) return;

        // Fetch initial telemetry
        this.bridge.getSystemTelemetry((res) => {
            if (res) this.updateTelemetryHUD(JSON.parse(res));
        });

        // Fetch Debloat Catalog
        this.bridge.getDebloatCatalog((res) => {
            if (res) {
                this.debloatCatalog = JSON.parse(res);
                this.renderDebloatOptions();
                this.applyDebloatPreset('standard');
            }
        });

        // Restore Priming Stack state from persistent storage
        this.restorePrimingState();
    }

    loadMockData() {
        this.updateTelemetryHUD({
            os: "Windows 11 Pro 64-bit",
            cpu_percent: 18.5,
            ram_percent: 42.0,
            ram_used_gb: 6.8,
            ram_total_gb: 16.0,
            disk_percent: 54.0,
            disk_free_gb: 215.4,
            uptime: "3h 42m 10s",
            is_admin: true
        });
        this.restorePrimingState();
    }

    bindEvents() {
        // Navigation Tabs
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const targetView = tab.getAttribute('data-view');
                this.switchView(targetView);
                if (window.cyberAudio) window.cyberAudio.playClick();
            });
        });

        // Telemetry HUD Matrix Collapse / Expand Shutter Toggle
        const btnToggleTelemetry = document.getElementById('btn-toggle-telemetry');
        if (btnToggleTelemetry) {
            btnToggleTelemetry.addEventListener('click', () => {
                this.toggleTelemetryHUD();
            });
        }

        // Quick Dashboard Action Buttons
        document.getElementById('btn-quick-deploy')?.addEventListener('click', () => {
            this.switchView('deployment');
            cyberAudio.click();
        });
        document.getElementById('btn-quick-prime')?.addEventListener('click', () => {
            this.switchView('priming');
            cyberAudio.click();
        });
        document.getElementById('btn-quick-debloat')?.addEventListener('click', () => {
            this.switchView('debloat');
            cyberAudio.click();
        });

        // Header Actions
        document.getElementById('btn-quick-restore')?.addEventListener('click', () => {
            cyberAudio.restorePoint();
            this.logTerminal("INFO", "[SHIELD] Requesting System Restore Point creation...");
            if (this.bridge) {
                this.bridge.createRestorePoint("mefresh_Manual_Snapshot");
            }
        });

        document.getElementById('btn-audio-toggle')?.addEventListener('click', () => {
            cyberAudio.muted = !cyberAudio.muted;
            const icon = document.getElementById('icon-audio');
            if (cyberAudio.muted) {
                icon.style.opacity = '0.3';
            } else {
                icon.style.opacity = '1';
                cyberAudio.click();
            }
        });

        // Priming & Search Events
        document.getElementById('btn-search-online')?.addEventListener('click', () => {
            this.triggerPackageSearch();
        });

        document.getElementById('input-pkg-search')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.triggerPackageSearch();
            }
        });

        document.getElementById('btn-close-search')?.addEventListener('click', () => {
            document.getElementById('search-results-panel').style.display = 'none';
            cyberAudio.click();
        });

        document.querySelectorAll('.quick-pick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.getAttribute('data-query');
                const input = document.getElementById('input-pkg-search');
                if (input) input.value = query;
                this.triggerPackageSearch(query);
                cyberAudio.click();
            });
        });

        document.getElementById('btn-add-local-file')?.addEventListener('click', () => {
            cyberAudio.click();
            if (this.bridge) {
                this.bridge.openFileDialog((res) => {
                    if (res) {
                        const fileInfo = JSON.parse(res);
                        this.addPackageToPrimingStack(fileInfo);
                        cyberAudio.packageAdd();
                    }
                });
            }
        });

        document.getElementById('btn-clear-queue')?.addEventListener('click', () => {
            if (confirm("Clear all software from priming stack?")) {
                this.primedPackages = [];
                this.renderPrimingTable();
                this.persistPrimingState();
                if (this.bridge && this.bridge.clearPrimingState) {
                    this.bridge.clearPrimingState();
                }
                cyberAudio.click();
            }
        });

        // Bundle Name persistence
        document.getElementById('input-bundle-name')?.addEventListener('input', () => {
            this.persistPrimingState();
        });

        // Save state before window closes
        window.addEventListener('beforeunload', () => {
            this.persistPrimingState();
        });

        // Bundle Generation
        document.getElementById('btn-generate-bundle')?.addEventListener('click', () => {
            this.initiateBundleGeneration();
        });

        // Deployment Events
        document.getElementById('btn-load-bundle-file')?.addEventListener('click', () => {
            cyberAudio.click();
            if (this.bridge) {
                this.bridge.openBundleFileDialog((filePath) => {
                    if (filePath) {
                        this.loadBundleFile(filePath);
                    }
                });
            }
        });

        document.getElementById('btn-start-deployment')?.addEventListener('click', () => {
            this.startDeploymentSequence();
        });

        document.getElementById('btn-pause-deployment')?.addEventListener('click', () => {
            if (this.bridge) this.bridge.pauseDeployment();
            cyberAudio.click();
        });

        document.getElementById('btn-cancel-deployment')?.addEventListener('click', () => {
            if (confirm("Are you sure you want to cancel the deployment sequence?")) {
                if (this.bridge) this.bridge.cancelDeployment();
                cyberAudio.warning();
            }
        });

        document.getElementById('btn-copy-terminal')?.addEventListener('click', () => {
            const terminal = document.getElementById('cyber-terminal-logs');
            if (terminal) {
                navigator.clipboard.writeText(terminal.innerText);
                alert("Terminal logs copied to clipboard!");
            }
        });

        document.getElementById('btn-clear-terminal')?.addEventListener('click', () => {
            const terminal = document.getElementById('cyber-terminal-logs');
            if (terminal) terminal.innerHTML = '';
        });

        // Debloat Presets
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const preset = btn.getAttribute('data-preset');
                this.applyDebloatPreset(preset);
                cyberAudio.click();
            });
        });

        // Debloat Execution
        document.getElementById('btn-execute-debloat')?.addEventListener('click', () => {
            this.executeDebloatSequence();
        });

        // Settings Events
        document.getElementById('setting-sound-enabled')?.addEventListener('change', (e) => {
            cyberAudio.setMuted(!e.target.checked);
        });

        document.getElementById('setting-sound-volume')?.addEventListener('input', (e) => {
            cyberAudio.setVolume(parseFloat(e.target.value));
        });

        document.getElementById('btn-test-sound')?.addEventListener('click', () => {
            cyberAudio.completeFanfare();
        });

        document.getElementById('btn-test-shield')?.addEventListener('click', () => {
            cyberAudio.restorePoint();
        });

        document.getElementById('btn-manual-restore-now')?.addEventListener('click', () => {
            cyberAudio.restorePoint();
            if (this.bridge) this.bridge.createRestorePoint("mefresh_Manual_Snapshot");
        });

        // SysInfo & Diagnostics Events
        document.querySelectorAll('.cat-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                this.sysInfoActiveCat = pill.getAttribute('data-cat') || 'summary';
                this.renderSysInfoContent();
                if (window.cyberAudio) window.cyberAudio.click();
            });
        });

        document.getElementById('sysinfo-search-input')?.addEventListener('input', (e) => {
            this.sysInfoFilterText = e.target.value.toLowerCase().trim();
            this.renderSysInfoContent();
        });

        document.getElementById('btn-sysinfo-refresh')?.addEventListener('click', () => {
            if (window.cyberAudio) window.cyberAudio.click();
            this.fetchSysInfo(true);
        });

        document.getElementById('btn-sysinfo-copy')?.addEventListener('click', () => {
            if (this.bridge) {
                this.bridge.exportSysInfoMarkdown((md) => {
                    if (md) {
                        navigator.clipboard.writeText(md);
                        if (window.cyberAudio) window.cyberAudio.itemSuccess();
                        alert("Diagnostics profile copied to clipboard as Markdown!");
                    }
                });
            }
        });

        document.getElementById('btn-launch-msinfo')?.addEventListener('click', () => {
            if (window.cyberAudio) window.cyberAudio.completeFanfare();
            if (this.bridge) this.bridge.launchMsInfo();
        });

        // Modal Events
        document.getElementById('btn-modal-close')?.addEventListener('click', () => this.closeEditModal());
        document.getElementById('btn-modal-cancel')?.addEventListener('click', () => this.closeEditModal());
        document.getElementById('btn-modal-save')?.addEventListener('click', () => this.saveEditedPackage());
    }

    switchView(viewName) {
        document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
        document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));

        const targetSection = document.getElementById(`view-${viewName}`);
        const targetTab = document.querySelector(`.nav-tab[data-view="${viewName}"]`);

        if (targetSection) targetSection.classList.add('active');
        if (targetTab) targetTab.classList.add('active');

        if (viewName === 'sysinfo') {
            this.fetchSysInfo(false);
        }
    }

    fetchSysInfo(force = false) {
        if (!this.bridge) return;
        if (this.sysInfoData && !force) {
            this.renderSysInfoContent();
            return;
        }

        const countEl = document.getElementById('sysinfo-timestamp');
        if (countEl) countEl.innerText = 'SCANNING...';

        this.bridge.getSysInfoDetails((resStr) => {
            try {
                this.sysInfoData = JSON.parse(resStr);
                const tsEl = document.getElementById('sysinfo-timestamp');
                if (tsEl) tsEl.innerText = this.sysInfoData.timestamp || 'LIVE';

                // Populate Hero Cards
                const sum = this.sysInfoData.summary || {};
                const elHeroOs = document.getElementById('sysinfo-hero-os');
                const elHeroOsBuild = document.getElementById('sysinfo-hero-os-build');
                const elHeroBoard = document.getElementById('sysinfo-hero-board');
                const elHeroMfg = document.getElementById('sysinfo-hero-mfg');
                const elHeroCpu = document.getElementById('sysinfo-hero-cpu');
                const elHeroCpuCores = document.getElementById('sysinfo-hero-cpu-cores');
                const elHeroRam = document.getElementById('sysinfo-hero-ram');
                const elHeroRamSpeed = document.getElementById('sysinfo-hero-ram-speed');

                if (elHeroOs) elHeroOs.innerText = sum.os_name || 'Windows 11';
                if (elHeroOsBuild) elHeroOsBuild.innerText = sum.os_version || 'x64';
                if (elHeroBoard) elHeroBoard.innerText = sum.system_model || 'PRO B650M-P';
                if (elHeroMfg) elHeroMfg.innerText = sum.system_manufacturer || 'MSI';
                if (elHeroCpu) elHeroCpu.innerText = sum.processor ? sum.processor.split(' ')[0] + ' ' + (sum.processor.split(' ')[1] || '') : 'CPU';
                if (elHeroCpuCores) elHeroCpuCores.innerText = sum.cores_threads || 'Cores / Threads';
                if (elHeroRam) elHeroRam.innerText = sum.total_physical_memory || 'RAM';
                if (elHeroRamSpeed) elHeroRamSpeed.innerText = sum.ram_speed || 'DDR5';

                this.renderSysInfoContent();
            } catch (e) {
                console.error("Failed to parse sysinfo details:", e);
            }
        });
    }

    renderSysInfoContent() {
        if (!this.sysInfoData) return;

        const container = document.getElementById('sysinfo-details-container');
        const titleEl = document.getElementById('sysinfo-category-title');
        const countEl = document.getElementById('sysinfo-item-count');
        if (!container) return;

        container.innerHTML = '';
        const cat = this.sysInfoActiveCat || 'summary';
        const filter = this.sysInfoFilterText || '';

        if (cat === 'summary') {
            if (titleEl) titleEl.innerText = "System Summary Diagnostics";
            const sum = this.sysInfoData.summary || {};
            const keys = Object.keys(sum);
            const filteredKeys = keys.filter(k => {
                if (!filter) return true;
                return k.toLowerCase().includes(filter) || String(sum[k]).toLowerCase().includes(filter);
            });

            if (countEl) countEl.innerText = `${filteredKeys.length} Properties`;

            const grid = document.createElement('div');
            grid.className = 'sysinfo-grid-2';

            filteredKeys.forEach(k => {
                const label = k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                const row = document.createElement('div');
                row.className = 'sysinfo-prop-row';
                row.innerHTML = `
                    <span class="sysinfo-prop-key">${label}</span>
                    <span class="sysinfo-prop-val" title="${sum[k]}">${sum[k]}</span>
                `;
                grid.appendChild(row);
            });
            container.appendChild(grid);
        } else if (cat === 'gpus') {
            if (titleEl) titleEl.innerText = "Dual GPU Adapters & Display Profile";
            const gpus = this.sysInfoData.gpus || [];
            const filteredGpus = gpus.filter(g => {
                if (!filter) return true;
                return g.name.toLowerCase().includes(filter) || g.type.toLowerCase().includes(filter);
            });

            if (countEl) countEl.innerText = `${filteredGpus.length} GPUs Detected`;

            filteredGpus.forEach(g => {
                const card = document.createElement('div');
                card.className = 'cyber-card sysinfo-card-highlight';
                card.style.background = 'rgba(255, 255, 255, 0.03)';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:18px;">🎮</span>
                            <div>
                                <div style="font-size:15px; font-weight:800; color:#fff;">${g.name}</div>
                                <span class="badge-tag ${g.type.includes('Dedicated') ? 'badge-purple' : 'badge-green'}" style="font-size:10px;">${g.type}</span>
                            </div>
                        </div>
                        <span class="badge-tag badge-cyan">${g.status}</span>
                    </div>
                    <div class="sysinfo-grid-2">
                        <div class="sysinfo-prop-row"><span class="sysinfo-prop-key">Video Memory (VRAM)</span><span class="sysinfo-prop-val">${g.vram}</span></div>
                        <div class="sysinfo-prop-row"><span class="sysinfo-prop-key">Driver Version</span><span class="sysinfo-prop-val">${g.driver_version}</span></div>
                        <div class="sysinfo-prop-row"><span class="sysinfo-prop-key">Display Resolution</span><span class="sysinfo-prop-val">${g.resolution}</span></div>
                    </div>
                `;
                container.appendChild(card);
            });
        } else if (cat === 'disks') {
            if (titleEl) titleEl.innerText = "Storage Drives & Volumes";
            const disks = this.sysInfoData.disks || [];
            const filteredDisks = disks.filter(d => {
                if (!filter) return true;
                return d.drive.toLowerCase().includes(filter) || d.filesystem.toLowerCase().includes(filter);
            });

            if (countEl) countEl.innerText = `${filteredDisks.length} Drives Active`;

            filteredDisks.forEach(d => {
                const card = document.createElement('div');
                card.className = 'cyber-card';
                card.style.background = 'rgba(255, 255, 255, 0.03)';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span class="badge-tag badge-cyan" style="font-size:12px; font-weight:800;">${d.drive}</span>
                            <span style="font-size:13px; font-weight:700; color:#fff;">Mount: ${d.mountpoint} (${d.filesystem})</span>
                        </div>
                        <span style="font-family:var(--font-mono); font-size:13px; font-weight:700; color:var(--text-cyan);">${d.free_gb} GB Free / ${d.total_gb} GB</span>
                    </div>
                    <div class="progress-container" style="height:6px; margin:6px 0;">
                        <div class="${d.drive === 'C:' ? 'progress-bar-cyan' : 'progress-bar-purple'}" style="width: ${d.used_percent}%;"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-dim);">
                        <span>Capacity Used: ${d.used_percent}%</span>
                        <span>Total Volume Size: ${d.total_gb} GB</span>
                    </div>
                `;
                container.appendChild(card);
            });
        } else if (cat === 'network') {
            if (titleEl) titleEl.innerText = "Network Adapters & Connectivity";
            const network = this.sysInfoData.network || [];
            const filteredNet = network.filter(n => {
                if (!filter) return true;
                return n.interface.toLowerCase().includes(filter) || n.ipv4.includes(filter);
            });

            if (countEl) countEl.innerText = `${filteredNet.length} Interfaces`;

            filteredNet.forEach(n => {
                const card = document.createElement('div');
                card.className = 'cyber-card';
                card.style.background = 'rgba(255, 255, 255, 0.03)';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="font-size:16px;">🌐</span>
                            <span style="font-size:14px; font-weight:700; color:#fff;">${n.interface}</span>
                        </div>
                        <span class="badge-tag badge-green">${n.status}</span>
                    </div>
                    <div class="sysinfo-grid-2">
                        <div class="sysinfo-prop-row"><span class="sysinfo-prop-key">IPv4 Address</span><span class="sysinfo-prop-val">${n.ipv4}</span></div>
                        <div class="sysinfo-prop-row"><span class="sysinfo-prop-key">MAC Physical Address</span><span class="sysinfo-prop-val">${n.mac}</span></div>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    }

    toggleTelemetryHUD() {
        this.isTelemetryVisible = !this.isTelemetryVisible;
        const wrapper = document.getElementById('telemetry-hud-wrapper');
        const btn = document.getElementById('btn-toggle-telemetry');
        const icon = document.getElementById('telemetry-toggle-icon');
        const text = document.getElementById('telemetry-toggle-text');
        const pulse = document.getElementById('hud-pulse-dot');
        const badge = document.getElementById('hud-status-badge');

        if (!this.isTelemetryVisible) {
            if (wrapper) wrapper.classList.add('collapsed');
            if (btn) btn.classList.add('suspended');
            if (icon) icon.innerText = '◇';
            if (text) text.innerText = 'EXPAND HUD';
            if (pulse) pulse.classList.add('suspended');
            if (badge) {
                badge.innerText = 'STREAM SUSPENDED (0% CPU)';
                badge.className = 'badge-tag badge-amber';
            }

            if (this.bridge && this.bridge.setTelemetryActive) {
                this.bridge.setTelemetryActive(false);
            }
            if (window.cyberAudio) window.cyberAudio.playHover();
            this.logTerminal("WARN", "[TELEMETRY] HUD matrix collapsed. Background telemetry polling & sampling paused (0.0% CPU).");
        } else {
            if (wrapper) wrapper.classList.remove('collapsed');
            if (btn) btn.classList.remove('suspended');
            if (icon) icon.innerText = '◈';
            if (text) text.innerText = 'COLLAPSE HUD';
            if (pulse) pulse.classList.remove('suspended');
            if (badge) {
                badge.innerText = 'ACTIVE STREAM (200ms)';
                badge.className = 'badge-tag badge-cyan';
            }

            if (this.bridge && this.bridge.setTelemetryActive) {
                this.bridge.setTelemetryActive(true);
            }
            if (window.cyberAudio) window.cyberAudio.playSuccess();
            this.logTerminal("INFO", "[TELEMETRY] HUD matrix expanded. Live hardware telemetry stream resumed.");
        }
    }

    updateTelemetryHUD(data) {
        if (!data || !this.isTelemetryVisible) return;

        const cpuVal = typeof data.cpu_percent === 'number' ? data.cpu_percent : 0;
        const ramVal = typeof data.ram_percent === 'number' ? data.ram_percent : 0;
        const gpuVal = typeof data.gpu_util_percent === 'number' ? data.gpu_util_percent : 0;

        // CPU Elements
        const elCpu = document.getElementById('hud-cpu');
        const elCpuBar = document.getElementById('hud-cpu-bar');
        const elCpuFreq = document.getElementById('hud-cpu-freq');
        const elCpuCores = document.getElementById('hud-cpu-cores');
        const elCpuTemp = document.getElementById('hud-cpu-temp');
        const elCpuTop = document.getElementById('hud-cpu-top');

        if (elCpu) elCpu.innerText = `${cpuVal.toFixed(1)}%`;
        if (elCpuBar) elCpuBar.style.width = `${Math.min(cpuVal, 100)}%`;
        if (elCpuFreq && data.cpu_freq_ghz) elCpuFreq.innerText = `⚡ ${data.cpu_freq_ghz.toFixed(2)} GHz`;
        if (elCpuCores && data.cpu_cores) elCpuCores.innerText = data.cpu_cores;
        if (elCpuTemp) elCpuTemp.innerText = `${(data.cpu_temp_c || 45.0).toFixed(1)}°C`;
        if (elCpuTop && data.top_cpu_process) {
            elCpuTop.innerText = data.top_cpu_process.name !== '-' ? `Top: ${data.top_cpu_process.name} (${data.top_cpu_process.percent}%)` : 'Top: -';
        }

        // Dual GPU Elements
        const elGpuUtil = document.getElementById('hud-gpu-util');
        const elGpuBar = document.getElementById('hud-gpu-bar');
        const elGpuName = document.getElementById('hud-gpu-name');
        const elGpuTemp = document.getElementById('hud-gpu-temp');
        const elGpuVram = document.getElementById('hud-gpu-vram');
        const elIgpuBadge = document.getElementById('hud-igpu-badge');
        const elGpuTop = document.getElementById('hud-gpu-top');

        if (elGpuUtil) elGpuUtil.innerText = `${gpuVal.toFixed(0)}%`;
        if (elGpuBar) elGpuBar.style.width = `${Math.min(gpuVal, 100)}%`;
        if (elGpuName && data.gpu_name) elGpuName.innerText = data.gpu_name;
        if (elGpuTemp) elGpuTemp.innerText = `${data.gpu_temp_c || 0}°C`;
        if (elGpuVram) elGpuVram.innerText = `VRAM: ${data.gpu_vram_used_gb || 0} / ${data.gpu_vram_total_gb || 0} GB`;
        if (elIgpuBadge) {
            elIgpuBadge.innerText = `iGPU: ${(data.igpu_util_percent || 0).toFixed(0)}%`;
        }
        if (elGpuTop && data.top_gpu_process) {
            elGpuTop.innerText = data.top_gpu_process.name !== '-' ? `Top: ${data.top_gpu_process.name}` : 'Top: -';
        }

        // RAM Elements
        const elRam = document.getElementById('hud-ram');
        const elRamBar = document.getElementById('hud-ram-bar');
        const elRamMeta = document.getElementById('hud-ram-meta');
        const elRamSpeed = document.getElementById('hud-ram-speed');

        if (elRam) elRam.innerText = `${ramVal.toFixed(1)}%`;
        if (elRamBar) elRamBar.style.width = `${Math.min(ramVal, 100)}%`;
        if (elRamMeta) elRamMeta.innerText = `${data.ram_used_gb || 0} GB / ${data.ram_total_gb || 0} GB`;
        if (elRamSpeed && data.ram_speed) elRamSpeed.innerText = `⚡ ${data.ram_speed}`;

        // Separate Drives Storage & Real-Time I/O (In-Place Cached Update for 0.0% GC overhead)
        const drivesContainer = document.getElementById('hud-drives-container');
        const drivesCount = document.getElementById('hud-drives-count');


        if (drivesContainer && Array.isArray(data.drives) && data.drives.length > 0) {
            if (drivesCount) drivesCount.innerText = `${data.drives.length} Drives Active`;

            // Check if drive count or letters changed to determine if DOM structure needs recreation
            const driveKeys = data.drives.map(d => d.letter).join('|');
            if (this._cachedDriveKeys !== driveKeys) {
                this._cachedDriveKeys = driveKeys;
                drivesContainer.innerHTML = data.drives.map(d => {
                    const safeKey = d.letter.replace(/[^a-zA-Z0-9]/g, '');
                    return `
                    <div id="drive-box-${safeKey}" style="display:flex; align-items:center; justify-content:space-between; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px; padding:6px 10px;">
                        <div style="display:flex; align-items:center; gap:8px; min-width:110px;">
                            <span class="badge-tag ${d.letter === 'C:' ? 'badge-cyan' : 'badge-purple'}" style="font-size:11px; padding:2px 6px; font-weight:800;">${d.letter}</span>
                            <span id="drive-free-${safeKey}" style="font-size:12px; font-weight:600; color:var(--text-main);">${d.free_gb} GB free</span>
                        </div>
                        <div style="flex:1; margin: 0 12px;">
                            <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--text-muted); margin-bottom:2px;">
                                <span id="drive-cap-${safeKey}">Capacity: ${d.percent_used}% (${d.total_gb} GB)</span>
                            </div>
                            <div class="progress-container" style="margin:0; height:4px; background:rgba(255,255,255,0.05);">
                                <div id="drive-bar-${safeKey}" class="${d.letter === 'C:' ? 'progress-bar-cyan' : 'progress-bar-purple'}" style="width: ${Math.min(d.percent_used, 100)}%;"></div>
                            </div>
                        </div>
                        <div style="display:flex; gap:10px; font-size:12px; font-weight:700; min-width:170px; justify-content:flex-end;">
                            <span id="drive-read-${safeKey}" style="color:var(--text-muted);">▼ R: 0.0 MB/s</span>
                            <span id="drive-write-${safeKey}" style="color:var(--text-muted);">▲ W: 0.0 MB/s</span>
                        </div>
                    </div>`;
                }).join('');
            }

            // In-place text update without reconstructing DOM nodes
            data.drives.forEach(d => {
                const safeKey = d.letter.replace(/[^a-zA-Z0-9]/g, '');
                const rEl = document.getElementById(`drive-read-${safeKey}`);
                const wEl = document.getElementById(`drive-write-${safeKey}`);
                const freeEl = document.getElementById(`drive-free-${safeKey}`);
                const capEl = document.getElementById(`drive-cap-${safeKey}`);
                const barEl = document.getElementById(`drive-bar-${safeKey}`);

                const rSpeed = (d.read_mbps || 0).toFixed(1);
                const wSpeed = (d.write_mbps || 0).toFixed(1);

                if (rEl) {
                    rEl.innerText = `▼ R: ${rSpeed} MB/s`;
                    rEl.style.color = d.read_mbps > 0 ? 'var(--cyan-primary)' : 'var(--text-muted)';
                }
                if (wEl) {
                    wEl.innerText = `▲ W: ${wSpeed} MB/s`;
                    wEl.style.color = d.write_mbps > 0 ? 'var(--purple-primary)' : 'var(--text-muted)';
                }
                if (freeEl) freeEl.innerText = `${d.free_gb} GB free`;
                if (capEl) capEl.innerText = `Capacity: ${d.percent_used}% (${d.total_gb} GB)`;
                if (barEl) barEl.style.width = `${Math.min(d.percent_used, 100)}%`;
            });
        }

        // Network I/O
        const elNetDown = document.getElementById('hud-net-down');
        const elNetUp = document.getElementById('hud-net-up');
        const elNetBar = document.getElementById('hud-net-bar');

        const netDownMbps = (data.net_down_mbps || 0) * 8;
        const netUpMbps = (data.net_up_mbps || 0) * 8;
        const totalNetMbps = netDownMbps + netUpMbps;

        if (elNetDown) elNetDown.innerText = `▼ Down: ${netDownMbps >= 1 ? netDownMbps.toFixed(1) + ' Mbps' : (data.net_down_mbps * 1024).toFixed(0) + ' KB/s'}`;
        if (elNetUp) elNetUp.innerText = `▲ Up: ${netUpMbps >= 1 ? netUpMbps.toFixed(1) + ' Mbps' : (data.net_up_mbps * 1024).toFixed(0) + ' KB/s'}`;
        
        // Logarithmically scaled and smoothed network bar
        const rawNetPct = totalNetMbps > 0 ? Math.min(Math.max(Math.log10(totalNetMbps + 1) * 35, 6), 100) : 4;
        this._currentNetBarPct = typeof this._currentNetBarPct === 'number' ? (this._currentNetBarPct * 0.7) + (rawNetPct * 0.3) : rawNetPct;
        if (elNetBar) elNetBar.style.width = `${Math.round(this._currentNetBarPct)}%`;

        // System OS & Uptime
        const elUptime = document.getElementById('hud-uptime');
        const elOs = document.getElementById('hud-os');
        const elAdminText = document.getElementById('admin-status-text');

        if (elUptime && data.uptime) elUptime.innerText = `Uptime: ${data.uptime}`;
        if (elOs && data.os) elOs.innerText = `${data.os} (${data.arch || 'x64'})`;

        if (elAdminText) {
            elAdminText.innerText = data.is_admin ? "ADMIN ELEVATED" : "STANDARD USER";
            const pill = document.getElementById('admin-status-pill');
            if (pill) {
                pill.style.borderColor = data.is_admin ? 'rgba(0, 255, 136, 0.3)' : 'rgba(255, 170, 0, 0.3)';
            }
        }

        // Push to History Buffers
        this.cpuHistory.push(cpuVal);
        this.cpuHistory.shift();

        this.ramHistory.push(ramVal);
        this.ramHistory.shift();

        // Draw Real-Time Sparklines
        this.drawSparkline('cpu-sparkline', this.cpuHistory, '#00f0ff', 'rgba(0, 240, 255, 0.15)');
        this.drawSparkline('ram-sparkline', this.ramHistory, '#00ff88', 'rgba(0, 255, 136, 0.15)');
    }

    drawSparkline(canvasId, dataPoints, strokeColor, fillColor) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        const step = w / (dataPoints.length - 1);
        ctx.beginPath();
        dataPoints.forEach((val, i) => {
            const normalizedY = h - (Math.min(Math.max(val, 0), 100) / 100) * (h - 4) - 2;
            const x = i * step;
            if (i === 0) ctx.moveTo(x, normalizedY);
            else ctx.lineTo(x, normalizedY);
        });

        // Stroke line
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Fill area
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        ctx.fillStyle = fillColor;
        ctx.fill();
    }

    // --- PRIMING & PACKAGE SEARCH ---

    triggerPackageSearch(forcedQuery = "") {
        const query = forcedQuery || document.getElementById('input-pkg-search')?.value.trim();
        if (!query) return;

        cyberAudio.click();
        const resultsPanel = document.getElementById('search-results-panel');
        const resultsList = document.getElementById('search-results-list');
        if (resultsPanel) resultsPanel.style.display = 'block';
        if (resultsList) {
            resultsList.innerHTML = `<div style="text-align:center; color:var(--cyan-primary); padding:16px;">Searching repository for '${query}'...</div>`;
        }

        if (this.bridge) {
            this.bridge.searchPackages(query);
        }
    }

    renderSearchResults(results) {
        const resultsList = document.getElementById('search-results-list');
        if (!resultsList) return;

        if (!results || results.length === 0) {
            resultsList.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:16px;">No packages found for this query.</div>`;
            return;
        }

        resultsList.innerHTML = '';
        results.forEach(item => {
            const row = document.createElement('div');
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.justifyContent = 'space-between';
            row.style.background = 'rgba(5, 8, 17, 0.6)';
            row.style.padding = '10px 14px';
            row.style.borderRadius = '6px';
            row.style.border = '1px solid var(--border-subtle)';

            row.innerHTML = `
                <div style="flex:1;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-weight:700; color:#fff;">${item.name}</span>
                        <span class="badge-tag badge-cyan">${item.version || 'Latest'}</span>
                        <span class="badge-tag badge-purple">${item.category || 'General'}</span>
                    </div>
                    <div style="font-size:12px; color:var(--text-dim); margin-top:2px;">${item.description || item.id}</div>
                </div>
                <div id="btn-wrap-${item.id.replace(/[^a-zA-Z0-9]/g, '_')}">
                    <button class="btn-cyber btn-primary download-pkg-btn" style="padding:6px 14px; font-size:12px;">
                        Download & Prime
                    </button>
                </div>
            `;

            const btn = row.querySelector('.download-pkg-btn');
            btn.addEventListener('click', () => {
                this.initiatePackageDownload(item, row);
            });

            resultsList.appendChild(row);
        });
    }

    initiatePackageDownload(pkg, rowEl) {
        cyberAudio.click();
        const safeId = pkg.id.replace(/[^a-zA-Z0-9]/g, '_');
        const wrap = document.getElementById(`btn-wrap-${safeId}`);
        if (wrap) {
            wrap.innerHTML = `<span style="font-family:var(--font-mono); font-size:12px; color:var(--cyan-primary);" id="prog-${safeId}">Downloading: 0%</span>`;
        }

        if (this.bridge) {
            this.bridge.downloadPackage(JSON.stringify(pkg));
        }
    }

    handleDownloadProgress(data) {
        const safeId = (data.id || '').replace(/[^a-zA-Z0-9]/g, '_');
        const progEl = document.getElementById(`prog-${safeId}`);

        if (data.status === 'downloading') {
            if (progEl) {
                progEl.innerText = `${data.percent}% (${data.downloaded_mb}/${data.total_mb} MB @ ${data.speed_mbps} MB/s)`;
            }
        } else if (data.status === 'completed') {
            if (progEl) {
                progEl.innerHTML = `<span class="badge-tag badge-green">Downloaded</span>`;
            }
            const res = data.result || {};
            if (res.file_path) {
                this.addPackageToPrimingStack({
                    id: data.id,
                    name: data.id,
                    file_path: res.file_path,
                    size_bytes: res.file_size || 0,
                    silent_args: "/quiet /norestart",
                    installer_type: "Standard"
                });
                cyberAudio.packageAdd();
            }
        } else if (data.status === 'failed') {
            if (progEl) {
                progEl.innerHTML = `<span class="badge-tag badge-red">Failed</span>`;
            }
            cyberAudio.warning();
        }
    }

    persistPrimingState() {
        const bundleName = document.getElementById('input-bundle-name')?.value.trim() || "";
        const payload = {
            items: this.primedPackages,
            bundle_name: bundleName,
            timestamp: new Date().toISOString()
        };
        const jsonStr = JSON.stringify(payload);
        try {
            localStorage.setItem('mefresh_priming_state', jsonStr);
        } catch (e) {}

        if (this.bridge && this.bridge.savePrimingState) {
            this.bridge.savePrimingState(jsonStr);
        }
    }

    restorePrimingState() {
        const applyState = (jsonStr) => {
            if (!jsonStr) return false;
            try {
                const data = JSON.parse(jsonStr);
                if (data && Array.isArray(data.items) && data.items.length > 0) {
                    this.primedPackages = data.items;
                    const bundleInput = document.getElementById('input-bundle-name');
                    if (bundleInput && data.bundle_name) {
                        bundleInput.value = data.bundle_name;
                    }
                    this.renderPrimingTable();
                    this.logTerminal("SUCCESS", `[PRIMING] Restored ${data.items.length} package(s) from previous session.`);
                    return true;
                }
            } catch (e) {
                console.error("Error restoring priming state", e);
            }
            return false;
        };

        if (this.bridge && this.bridge.loadPrimingState) {
            this.bridge.loadPrimingState((res) => {
                const loaded = applyState(res);
                if (!loaded) {
                    const localRes = localStorage.getItem('mefresh_priming_state');
                    applyState(localRes);
                }
            });
        } else {
            const localRes = localStorage.getItem('mefresh_priming_state');
            applyState(localRes);
        }
    }

    addPackageToPrimingStack(pkg) {
        // Prevent duplicate file paths
        const exists = this.primedPackages.some(p => p.file_path === pkg.file_path);
        if (!exists) {
            this.primedPackages.push({
                id: pkg.id || `app_${this.primedPackages.length + 1}`,
                name: pkg.name || "Unknown App",
                file_path: pkg.file_path,
                size_bytes: pkg.size_bytes || 0,
                category: pkg.category || "General",
                installer_type: pkg.installer_type || "Standard",
                silent_args: pkg.silent_args || "/quiet /norestart"
            });
            this.renderPrimingTable();
            this.persistPrimingState();
        }
    }

    renderPrimingTable() {
        const tbody = document.getElementById('priming-tbody');
        const countSpan = document.getElementById('primed-count');
        if (countSpan) countSpan.innerText = this.primedPackages.length;

        if (!tbody) return;

        if (this.primedPackages.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align:center; color:var(--text-muted); padding:30px;">
                        No software packages added yet. Search online or add local installers above to prime your fresh Windows setup.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = '';
        this.primedPackages.forEach((item, idx) => {
            const tr = document.createElement('tr');
            const sizeMB = (item.size_bytes / (1024 * 1024)).toFixed(1);

            tr.innerHTML = `
                <td style="font-family:var(--font-mono); font-weight:700; color:var(--cyan-primary);">${idx + 1}</td>
                <td>
                    <div style="font-weight:700; color:#fff;">${item.name}</div>
                    <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${item.file_path}</div>
                </td>
                <td><span class="badge-tag badge-purple">${item.category}</span></td>
                <td><span class="badge-tag badge-cyan">${item.installer_type}</span></td>
                <td><code style="font-family:var(--font-mono); font-size:12px; color:var(--text-cyan);">${item.silent_args || '(default silent)'}</code></td>
                <td style="font-family:var(--font-mono);">${sizeMB > 0 ? sizeMB + ' MB' : '-'}</td>
                <td style="text-align:right;">
                    <button class="btn-cyber btn-outline edit-switch-btn" style="padding:4px 8px; font-size:11px;" title="Edit Silent Switches">Edit</button>
                    <button class="btn-cyber btn-outline move-up-btn" style="padding:4px 8px; font-size:11px;" title="Move Up">▲</button>
                    <button class="btn-cyber btn-outline move-down-btn" style="padding:4px 8px; font-size:11px;" title="Move Down">▼</button>
                    <button class="btn-cyber btn-danger remove-pkg-btn" style="padding:4px 8px; font-size:11px;" title="Remove">✕</button>
                </td>
            `;

            tr.querySelector('.edit-switch-btn').addEventListener('click', () => this.openEditModal(idx));
            tr.querySelector('.move-up-btn').addEventListener('click', () => this.movePackage(idx, -1));
            tr.querySelector('.move-down-btn').addEventListener('click', () => this.movePackage(idx, 1));
            tr.querySelector('.remove-pkg-btn').addEventListener('click', () => this.removePackage(idx));

            tbody.appendChild(tr);
        });
    }

    openEditModal(idx) {
        this.currentEditIndex = idx;
        const item = this.primedPackages[idx];
        if (!item) return;

        document.getElementById('edit-pkg-name').value = item.name;
        document.getElementById('edit-pkg-args').value = item.silent_args;
        document.getElementById('modal-switch-editor').classList.add('active');
        cyberAudio.click();
    }

    closeEditModal() {
        document.getElementById('modal-switch-editor').classList.remove('active');
        cyberAudio.click();
    }

    saveEditedPackage() {
        if (this.currentEditIndex >= 0 && this.currentEditIndex < this.primedPackages.length) {
            this.primedPackages[this.currentEditIndex].name = document.getElementById('edit-pkg-name').value;
            this.primedPackages[this.currentEditIndex].silent_args = document.getElementById('edit-pkg-args').value;
            this.renderPrimingTable();
            this.persistPrimingState();
            this.closeEditModal();
        }
    }

    movePackage(idx, dir) {
        const target = idx + dir;
        if (target >= 0 && target < this.primedPackages.length) {
            const temp = this.primedPackages[idx];
            this.primedPackages[idx] = this.primedPackages[target];
            this.primedPackages[target] = temp;
            this.renderPrimingTable();
            this.persistPrimingState();
            cyberAudio.click();
        }
    }

    removePackage(idx) {
        this.primedPackages.splice(idx, 1);
        this.renderPrimingTable();
        this.persistPrimingState();
        cyberAudio.click();
    }

    // --- BUNDLE EXPORT ---

    initiateBundleGeneration() {
        if (this.primedPackages.length === 0) {
            alert("Please add at least one software package to the priming stack first.");
            return;
        }

        const bundleName = document.getElementById('input-bundle-name')?.value.trim() || "mefresh_deployment_bundle";
        cyberAudio.click();

        if (this.bridge) {
            this.bridge.saveBundleFileDialog(`${bundleName}.zip`, (savePath) => {
                if (savePath) {
                    this.logTerminal("INFO", `[BUNDLER] Generating portable bundle at: ${savePath}`);
                    const bundleData = {
                        bundle_name: bundleName,
                        output_path: savePath,
                        items: this.primedPackages,
                        options: {
                            auto_restore_point: true,
                            stop_on_error: false
                        }
                    };
                    this.bridge.createBundle(JSON.stringify(bundleData));
                }
            });
        }
    }

    handleBundleProgress(data) {
        if (data.status === 'packaging') {
            this.logTerminal("INFO", `[BUNDLER] Packing [${data.progress}%]: ${data.current_item}`);
        } else if (data.status === 'finished') {
            if (data.success) {
                cyberAudio.completeFanfare();
                this.logTerminal("SUCCESS", `[BUNDLER] ${data.message}`);
                alert(`Bundle Generated Successfully!\n\nPath: ${data.file_path}`);
            } else {
                cyberAudio.warning();
                this.logTerminal("ERROR", `[BUNDLER] ${data.message}`);
                alert(`Bundle creation failed: ${data.message}`);
            }
        }
    }

    // --- SILENT DEPLOYMENT ---

    loadBundleFile(zipPath) {
        if (!this.bridge) return;
        this.logTerminal("INFO", `[DEPLOYMENT] Extracting bundle archive: ${zipPath}...`);

        this.bridge.loadBundle(zipPath, (resStr) => {
            const res = JSON.parse(resStr);
            if (res.success) {
                cyberAudio.itemSuccess();
                this.deploymentQueue = res.manifest.packages || [];
                document.getElementById('loaded-bundle-label').innerText = `Loaded: ${res.manifest.bundle_name} (${this.deploymentQueue.length} pkgs)`;
                this.renderDeploymentQueue();
                this.logTerminal("SUCCESS", `[DEPLOYMENT] Bundle loaded with ${this.deploymentQueue.length} packages.`);
            } else {
                cyberAudio.warning();
                alert(`Failed to load bundle: ${res.message}`);
            }
        });
    }

    startDeploymentSequence() {
        // Use loaded bundle or primed stack
        const queueToUse = this.deploymentQueue.length > 0 ? this.deploymentQueue : this.primedPackages;

        if (queueToUse.length === 0) {
            alert("No packages in deployment queue. Prime packages or load a .zip bundle first.");
            return;
        }

        cyberAudio.deployStart();
        this.logTerminal("INFO", "[DEPLOYMENT] Initializing unattended silent deployment matrix...");

        document.getElementById('btn-start-deployment').style.display = 'none';
        document.getElementById('btn-pause-deployment').style.display = 'inline-flex';
        document.getElementById('btn-cancel-deployment').style.display = 'inline-flex';

        this.renderDeploymentQueue(queueToUse);
        this.startDeployTimer();

        const plan = {
            packages: queueToUse,
            options: {
                create_restore_point: document.getElementById('setting-restore-deploy')?.checked ?? true,
                stop_on_error: false
            }
        };

        if (this.bridge) {
            this.bridge.startDeployment(JSON.stringify(plan));
        }
    }

    renderDeploymentQueue(queue = this.deploymentQueue) {
        const container = document.getElementById('deployment-items-list');
        if (!container) return;

        container.innerHTML = '';
        queue.forEach((item, idx) => {
            const card = document.createElement('div');
            card.id = `deploy-item-${idx}`;
            card.style.display = 'flex';
            card.style.alignItems = 'center';
            card.style.justifyContent = 'space-between';
            card.style.background = 'var(--bg-glass)';
            card.style.padding = '10px 14px';
            card.style.borderRadius = '6px';
            card.style.border = '1px solid var(--border-subtle)';

            card.innerHTML = `
                <div style="display:flex; align-items:center; gap:12px;">
                    <span style="font-family:var(--font-mono); font-weight:700; color:var(--text-cyan);">#${idx + 1}</span>
                    <div>
                        <div style="font-weight:700; color:#fff;">${item.name}</div>
                        <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${item.installer_type}</div>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span class="badge-tag badge-cyan" id="status-badge-${idx}">QUEUED</span>
                </div>
            `;
            container.appendChild(card);
        });
    }

    handleInstallerEvent(evtType, data) {
        if (evtType === 'engine_started') {
            document.getElementById('deploy-stat-count').innerText = `0 / ${data.total}`;
        } else if (evtType === 'item_started') {
            cyberAudio.hover();
            const badge = document.getElementById(`status-badge-${data.index}`);
            const card = document.getElementById(`deploy-item-${data.index}`);
            if (badge) {
                badge.className = 'badge-tag badge-purple';
                badge.innerText = 'INSTALLING...';
            }
            if (card) {
                card.style.borderColor = 'var(--purple-primary)';
                card.style.boxShadow = '0 0 14px var(--purple-glow)';
            }
            document.getElementById('deploy-stat-current').innerText = `Installing: ${data.name}`;
            document.getElementById('deploy-stat-progress').innerText = `${data.progress}%`;
            document.getElementById('deploy-progress-bar').style.width = `${data.progress}%`;
        } else if (evtType === 'item_finished') {
            const badge = document.getElementById(`status-badge-${data.index}`);
            const card = document.getElementById(`deploy-item-${data.index}`);
            if (data.status === 'COMPLETED') {
                cyberAudio.itemSuccess();
                if (badge) {
                    badge.className = 'badge-tag badge-green';
                    badge.innerText = `COMPLETED (${data.duration_sec}s)`;
                }
                if (card) {
                    card.style.borderColor = 'var(--green-cyber)';
                    card.style.boxShadow = 'none';
                }
            } else {
                cyberAudio.itemFailed();
                if (badge) {
                    badge.className = 'badge-tag badge-red';
                    badge.innerText = `FAILED (Code ${data.exit_code})`;
                }
                if (card) {
                    card.style.borderColor = 'var(--red-danger)';
                    card.style.boxShadow = 'none';
                }
            }
        } else if (evtType === 'log') {
            this.logTerminal(data.level, data.message);
        } else if (evtType === 'engine_completed') {
            cyberAudio.completeFanfare();
            this.stopDeployTimer();
            document.getElementById('deploy-stat-progress').innerText = '100%';
            document.getElementById('deploy-progress-bar').style.width = '100%';
            document.getElementById('deploy-stat-current').innerText = 'All tasks completed';
            document.getElementById('deploy-stat-result').innerText = `Finished (${data.completed} OK, ${data.failed} Failed)`;

            document.getElementById('btn-start-deployment').style.display = 'inline-flex';
            document.getElementById('btn-pause-deployment').style.display = 'none';
            document.getElementById('btn-cancel-deployment').style.display = 'none';

            this.logTerminal("SUCCESS", `[DEPLOYMENT FINISHED] ${data.completed} succeeded, ${data.failed} failed in ${data.duration_sec}s.`);
            alert(`Deployment Completed!\n\nSuccessfully installed: ${data.completed}/${data.total} packages.`);
        }
    }

    startDeployTimer() {
        this.deployStartTime = Date.now();
        if (this.deployTimerInterval) clearInterval(this.deployTimerInterval);
        this.deployTimerInterval = setInterval(() => {
            const elapsedSec = Math.floor((Date.now() - this.deployStartTime) / 1000);
            const m = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
            const s = String(elapsedSec % 60).padStart(2, '0');
            document.getElementById('deploy-stat-timer').innerText = `${m}:${s}`;
        }, 1000);
    }

    stopDeployTimer() {
        if (this.deployTimerInterval) clearInterval(this.deployTimerInterval);
    }

    logTerminal(level, message) {
        const terminal = document.getElementById('cyber-terminal-logs');
        if (!terminal) return;

        const line = document.createElement('div');
        line.className = `terminal-line log-${level.toLowerCase()}`;
        line.innerText = message;

        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;
    }

    // --- DEBLOAT & OPTIMIZER ---

    renderDebloatOptions() {
        const appxContainer = document.getElementById('debloat-appx-container');
        const telemetryContainer = document.getElementById('debloat-telemetry-container');
        const systemContainer = document.getElementById('debloat-system-container');
        const servicesContainer = document.getElementById('debloat-services-container');

        if (appxContainer && this.debloatCatalog.appx) {
            appxContainer.innerHTML = '';
            this.debloatCatalog.appx.forEach(item => {
                appxContainer.appendChild(this.createToggleRow(item.id, item.name, item.safe, 'appx'));
            });
        }

        if (telemetryContainer && this.debloatCatalog.telemetry) {
            telemetryContainer.innerHTML = '';
            this.debloatCatalog.telemetry.forEach(item => {
                telemetryContainer.appendChild(this.createToggleRow(item.id, item.name, item.default, 'telemetry'));
            });
        }

        if (systemContainer && this.debloatCatalog.system) {
            systemContainer.innerHTML = '';
            this.debloatCatalog.system.forEach(item => {
                systemContainer.appendChild(this.createToggleRow(item.id, item.name, item.default, 'system'));
            });
        }

        if (servicesContainer && this.debloatCatalog.services) {
            servicesContainer.innerHTML = '';
            this.debloatCatalog.services.forEach(item => {
                servicesContainer.appendChild(this.createToggleRow(item.id, item.name, item.default, 'services'));
            });
        }
    }

    createToggleRow(id, label, defaultChecked, group) {
        const row = document.createElement('div');
        row.className = 'toggle-wrapper';
        row.innerHTML = `
            <span style="font-size:13px; color:var(--text-main);">${label}</span>
            <label class="switch">
                <input type="checkbox" id="debloat-${group}-${id}" data-group="${group}" data-id="${id}" ${defaultChecked ? 'checked' : ''}>
                <span class="slider"></span>
            </label>
        `;
        row.querySelector('input').addEventListener('change', () => cyberAudio.toggle());
        return row;
    }

    applyDebloatPreset(presetName) {
        if (!this.bridge) return;
        this.bridge.getDebloatPreset(presetName, (resStr) => {
            const preset = JSON.parse(resStr);
            this.setCheckboxGroup('appx', preset.selected_appx || []);
            this.setCheckboxGroup('telemetry', preset.selected_telemetry || []);
            this.setCheckboxGroup('system', preset.selected_system || []);
            this.setCheckboxGroup('services', preset.selected_services || []);
        });
    }

    setCheckboxGroup(group, selectedIds) {
        const inputs = document.querySelectorAll(`input[data-group="${group}"]`);
        inputs.forEach(inp => {
            inp.checked = selectedIds.includes(inp.getAttribute('data-id'));
        });
    }

    executeDebloatSequence() {
        const selectedAppx = this.getSelectedCheckboxIds('appx');
        const selectedTelemetry = this.getSelectedCheckboxIds('telemetry');
        const selectedSystem = this.getSelectedCheckboxIds('system');
        const selectedServices = this.getSelectedCheckboxIds('services');

        const totalSelected = selectedAppx.length + selectedTelemetry.length + selectedSystem.length + selectedServices.length;
        if (totalSelected === 0) {
            alert("No debloat options selected.");
            return;
        }

        if (!confirm(`Execute Windows Debloat & Optimization Matrix with ${totalSelected} operations?\n\nA System Restore Point will automatically be created.`)) {
            return;
        }

        cyberAudio.restorePoint();
        const pWrap = document.getElementById('debloat-prog-wrap');
        if (pWrap) pWrap.style.display = 'block';

        this.logTerminal("INFO", `[DEBLOAT] Initializing debloat matrix with ${totalSelected} operations...`);

        const config = {
            selected_appx: selectedAppx,
            selected_telemetry: selectedTelemetry,
            selected_system: selectedSystem,
            selected_services: selectedServices
        };

        if (this.bridge) {
            this.bridge.executeDebloat(JSON.stringify(config));
        }
    }

    getSelectedCheckboxIds(group) {
        const list = [];
        document.querySelectorAll(`input[data-group="${group}"]:checked`).forEach(inp => {
            list.push(inp.getAttribute('data-id'));
        });
        return list;
    }
}

// Instantiate App when DOM is loaded
window.addEventListener('DOMContentLoaded', () => {
    window.mefreshApp = new MeFreshApp();
});
