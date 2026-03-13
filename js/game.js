/**
 * Main Game Logic - Phaser 3
 * Handles the 64-bit Analog Defense System experience
 */

const gameConfig = {
    type: Phaser.AUTO,
    parent: 'game-container',
    width: 1000,
    height: 700,
    pixelArt: false,
    backgroundColor: '#000000',
    scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.NO_CENTER  // canvas anchors at 0,0 — keeps HTML UI layer aligned
    },
    scene: {
        preload: preload,
        create: create,
        update: update
    }
};

// Game is NOT created here — initGame() is called by auth.js after the
// container is visible so Phaser can measure real dimensions.
let game = null;

function initGame() {
    if (game) return;
    game = new Phaser.Game(gameConfig);
}

let statusText;
let terminalSprite;
let archivesSprite;
let bg;
let crtOverlay;
let radarSweep;
let pointsText;
let points = 0;

window.gameInterface = {
    setStatus: function(msg, isError) {
        if(statusText) {
            statusText.setText("> " + msg);
            statusText.setColor(isError ? '#ff3333' : '#00ff00');
        }
    },
    addPoints: function(amount) {
        points += amount;
        if(pointsText) {
            pointsText.setText("CREDITS: " + String(points).padStart(7, '0'));
            if (game) {
                game.scene.scenes[0].tweens.add({
                    targets: pointsText,
                    alpha: 0.5,
                    yoyo: true,
                    duration: 50,
                    repeat: 3
                });
            }
        }
    },
    // Called by create() once the scene is ready — boot flash + radar
    systemUnlock: function() {
        const scene = game && game.scene.scenes[0];
        if(!scene) return;

        const flash = scene.add.rectangle(500, 350, 1000, 700, 0xffffff);
        flash.setDepth(100);
        scene.tweens.add({
            targets: flash,
            alpha: 0,
            duration: 1500,
            ease: 'Expo.easeOut',
            onComplete: () => flash.destroy()
        });

        scene.tweens.add({
            targets: radarSweep,
            angle: 360,
            duration: 4000,
            repeat: -1
        });
    }
};

function preload() {
    // Optional CRT overlay; if missing (e.g. on GitHub Pages), create() skips it
    this.load.image('crt_overlay', 'assets/game/crt_overlay.png');
}

// Variables for starfield
let stars = [];
const numStars = 400;

function create() {
    // 1. Procedural Space Background (Starfield)
    // Create stars
    for (let i = 0; i < numStars; i++) {
        const star = this.add.circle(
            Phaser.Math.Between(0, 1000), 
            Phaser.Math.Between(0, 700), 
            Phaser.Math.FloatBetween(0.5, 2), 
            0xffffff, 
            Phaser.Math.FloatBetween(0.2, 1)
        );
        star.zDepth = Phaser.Math.FloatBetween(0.1, 1); // For parallax speed
        stars.push(star);
    }

    // Optional: Draw a subtle programmatic grid/wireframe for "defense system" look
    const grid = this.add.graphics();
    grid.lineStyle(1, 0x003300, 0.3);
    for(let i = 0; i < 1000; i += 50) {
        grid.moveTo(i, 0); grid.lineTo(i, 700);
    }
    for(let i = 0; i < 700; i += 50) {
        grid.moveTo(0, i); grid.lineTo(1000, i);
    }
    grid.strokePath();

    // 2. HUD Elements (Analog Radar style)
    const radarBase = this.add.circle(850, 150, 100, 0x003300, 0.4).setStrokeStyle(2, 0x00ff00, 0.5);
    this.add.circle(850, 150, 50).setStrokeStyle(1, 0x00ff00, 0.3);
    this.add.line(0, 0, 850, 50, 850, 250, 0x00ff00, 0.3).setOrigin(0,0);
    this.add.line(0, 0, 750, 150, 950, 150, 0x00ff00, 0.3).setOrigin(0,0);
    
    radarSweep = this.add.graphics();
    radarSweep.fillStyle(0x00ff00, 0.2);
    radarSweep.slice(850, 150, 100, Phaser.Math.DegToRad(0), Phaser.Math.DegToRad(45), false);
    radarSweep.fillPath();
    // Origin rotation requires a trick in graphics, or we just rotate the graphics object natively if we center it
    radarSweep.x = 850;
    radarSweep.y = 150;
    radarSweep.clear();
    radarSweep.fillStyle(0x00ff00, 0.3);
    radarSweep.slice(0, 0, 100, Phaser.Math.DegToRad(0), Phaser.Math.DegToRad(60), false);
    radarSweep.fillPath();

    // 3. System Title
    this.add.text(50, 40, 'GLOBAL COMMAND NETWORK', {
        fontFamily: '"VT323"',
        fontSize: '48px',
        color: '#00ff00',
        shadow: { offsetX: 0, offsetY: 0, color: '#00ff00', blur: 10, fill: true }
    });
    this.add.text(50, 90, 'STATUS: SECURE', {
        fontFamily: '"VT323"',
        fontSize: '24px',
        color: '#00aaaa'
    });

    // 4. Points Display (Credits)
    pointsText = this.add.text(50, 130, 'CREDITS: 0000000', {
        fontFamily: '"VT323"',
        fontSize: '32px',
        color: '#ffcc00',
        shadow: { offsetX: 0, offsetY: 0, color: '#ffcc00', blur: 5, fill: true }
    });

    // 5. Analog Control Panels (Buttons)
    terminalSprite = createAnalogPanel(this, 250, 600, 'COMM LINK [ NEW SECURE MESSAGE ]', openDialogBox);
    archivesSprite = createAnalogPanel(this, 750, 600, 'DATA CORE [ ACCESS RECORDS ]', openArchives);

    // 6. Global Status Box Background
    const uiBoxWidth = 900;
    const uiBoxHeight = 80;
    const uiBoxX = 500;
    const uiBoxY = 480;

    this.add.rectangle(uiBoxX, uiBoxY, uiBoxWidth, uiBoxHeight, 0x001100, 0.8).setStrokeStyle(2, 0x00ff00);
    
    statusText = this.add.text(70, 455, '> SYS: AWAITING INPUT', {
        fontFamily: '"VT323"',
        fontSize: '28px',
        color: '#00ff00',
        wordWrap: { width: 860 }
    });

    // 7. CRT Overlay details (Noise & Vignette) - optional if asset missing
    const scaleX = this.scale.scaleX ?? 1;
    const scaleY = this.scale.scaleY ?? 1;
    if (this.textures.exists('crt_overlay')) {
        crtOverlay = this.add.image(500, 350, 'crt_overlay');
        crtOverlay.setAlpha(0.3);
        crtOverlay.blendMode = Phaser.BlendModes.MULTIPLY;
        crtOverlay.setScale(Math.max(scaleX, scaleY));
    }

    // Close DOM elements if clicking background (Using an invisible zone since we removed the bg image)
    const interactionZone = this.add.zone(500, 350, 1000, 700).setInteractive();
    interactionZone.on('pointerdown', () => {
        document.getElementById('dialog-box').classList.remove('active');
    });

    // Add CRT flicker effect mapped to a blank rectangle over everything
    const flicker = this.add.rectangle(500, 350, 1000, 700, 0x000000);
    flicker.setAlpha(0.0);
    this.time.addEvent({
        delay: 50,
        callback: () => {
            if(Math.random() > 0.95) {
                flicker.setAlpha(Math.random() * 0.1);
            } else {
                flicker.setAlpha(0);
            }
        },
        loop: true
    });

    // Boot animation — runs immediately since the game only starts after login
    window.gameInterface.systemUnlock();
}

function createAnalogPanel(scene, x, y, textStr, callback) {
    const width = 450;
    const height = 70;
    const container = scene.add.container(x, y);

    // Metallic looking base
    const bgRect = scene.add.rectangle(0, 0, width, height, 0x112211).setStrokeStyle(3, 0x00aa00);
    const text = scene.add.text(0, 0, textStr, {
        fontFamily: '"VT323"',
        fontSize: '26px',
        color: '#00ff00',
        shadow: { blur: 5, color: '#00aa00', fill: true }
    }).setOrigin(0.5);

    container.add([bgRect, text]);
    
    container.setSize(width, height);
    container.setInteractive({ useHandCursor: true });

    container.on('pointerover', () => {
        bgRect.setFillStyle(0x00ff00);
        text.setColor('#000000');
        text.setShadow(0,0,'#000000',0);
    });

    container.on('pointerout', () => {
        bgRect.setFillStyle(0x112211);
        text.setColor('#00ff00');
        text.setShadow(0,0,'#00aa00',5,true);
    });

    container.on('pointerdown', callback);

    return container;
}

function update() { 
    // Animate starfield for a slow drift effect
    for (let i = 0; i < stars.length; i++) {
        let star = stars[i];
        star.x -= star.zDepth * 0.5; // move left
        
        // Reset if off screen
        if (star.x < 0) {
            star.x = 1000;
            star.y = Phaser.Math.Between(0, 700);
        }
    }
}

// ----- DOM Interaction logic -----

document.getElementById('game-query-input').addEventListener('keydown', function(e) {
    if(e.key === 'Enter') {
        const val = this.value;
        if(val.trim() !== '') {
            document.getElementById('query-input').value = val;
            document.getElementById('submit-btn').click();
            this.value = '';
            document.getElementById('dialog-box').classList.remove('active');
        }
    }
});

document.getElementById('close-archives').addEventListener('click', function() {
    document.getElementById('archives-panel').classList.remove('active');
});

function openDialogBox() {
    document.getElementById('archives-panel').classList.remove('active');
    const dialog = document.getElementById('dialog-box');
    dialog.classList.add('active');
    document.getElementById('game-query-input').focus();
}

function openArchives() {
    document.getElementById('dialog-box').classList.remove('active');
    document.getElementById('archives-panel').classList.add('active');
    if(window.appRefreshCohorts) {
        window.appRefreshCohorts();
    }
}
