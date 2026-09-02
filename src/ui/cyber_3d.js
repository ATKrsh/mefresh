/**
 * Cyber3D - Live 3D Holographic Quantum Core & Orbital Ring Visualizer
 */
class Cyber3DCore {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.rotX = 25;
        this.rotY = 45;
        this.autoSpinSpeed = 0.8;
        this.isHovered = false;

        this.init();
        this.bindEvents();
        this.animate();
    }

    init() {
        this.container.innerHTML = `
            <div class="cube-3d-scene">
                <div class="cube-3d-wrapper" id="core-3d-wrapper">
                    <!-- Orbital Rings -->
                    <div class="orbital-ring ring-1"></div>
                    <div class="orbital-ring ring-2"></div>
                    <div class="orbital-ring ring-3"></div>

                    <!-- Holographic Cube Faces -->
                    <div class="cube-face face-front"><div class="face-grid"></div></div>
                    <div class="cube-face face-back"><div class="face-grid"></div></div>
                    <div class="cube-face face-right"><div class="face-grid"></div></div>
                    <div class="cube-face face-left"><div class="face-grid"></div></div>
                    <div class="cube-face face-top"><div class="face-grid"></div></div>
                    <div class="cube-face face-bottom"><div class="face-grid"></div></div>

                    <!-- Inner Glow Core -->
                    <div class="inner-energy-core"></div>
                </div>
            </div>
        `;
        this.wrapper = this.container.querySelector('#core-3d-wrapper');
    }

    bindEvents() {
        this.container.addEventListener('mouseenter', () => {
            this.isHovered = true;
            cyberAudio.hover();
        });

        this.container.addEventListener('mouseleave', () => {
            this.isHovered = false;
        });

        this.container.addEventListener('mousemove', (e) => {
            const rect = this.container.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width - 0.5;
            const y = (e.clientY - rect.top) / rect.height - 0.5;
            this.rotY += x * 3;
            this.rotX -= y * 3;
        });
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        if (!this.isHovered) {
            this.rotY = (this.rotY + this.autoSpinSpeed) % 360;
            this.rotX = 22;
        } else {
            this.rotY = (this.rotY + this.autoSpinSpeed * 2.0) % 360;
            this.rotX = 22;
        }

        if (this.wrapper) {
            this.wrapper.style.transform = `rotateX(${this.rotX}deg) rotateY(${this.rotY}deg)`;
        }
    }
}

window.addEventListener('DOMContentLoaded', () => {
    new Cyber3DCore('header-3d-core');
    new Cyber3DCore('dashboard-3d-core');
});
