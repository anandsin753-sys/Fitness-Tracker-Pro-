(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const gameSection = document.querySelector("#running-john-game");
    const startButton = document.querySelector("#start-running-john");
    const restartButton = document.querySelector("#restart-running-john");
    const jumpButton = document.querySelector("#running-john-jump");
    const canvas = document.querySelector("#running-john-canvas");
    const scoreElement = document.querySelector("#running-john-score");
    const bestElement = document.querySelector("#running-john-best");

    if (
      !gameSection ||
      !startButton ||
      !restartButton ||
      !jumpButton ||
      !canvas ||
      !scoreElement ||
      !bestElement
    ) {
      return;
    }

    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const groundY = height - 82;
    const storageKey = "fitnessTrackerRunningJohnBest";

    let animationId = null;
    let lastTime = 0;
    let running = false;
    let ended = false;
    let score = 0;
    let bestScore = readBestScore();
    let speed = 6;
    let spawnTimer = 0;
    let sceneryOffset = 0;
    let stumbleFlash = 0;
    let obstacles = [];

    const john = {
      x: 162,
      y: groundY - 62,
      width: 38,
      height: 62,
      velocityY: 0,
      gravity: 0.78,
      jumpStrength: -15.5,
      onGround: true,
      stride: 0,
    };

    const monster = {
      gap: 132,
      minGap: 34,
      width: 68,
      height: 78,
    };

    updateScoreboard();
    drawIdleScreen();

    function readBestScore() {
      try {
        const stored = Number(window.localStorage.getItem(storageKey));
        return Number.isFinite(stored) && stored > 0 ? Math.floor(stored) : 0;
      } catch (error) {
        return 0;
      }
    }

    function saveBestScore(value) {
      bestScore = Math.max(bestScore, Math.floor(value));
      try {
        window.localStorage.setItem(storageKey, String(bestScore));
      } catch (error) {
        // Best score display still works for the current page if storage is blocked.
      }
    }

    function updateScoreboard() {
      scoreElement.textContent = `Score: ${Math.floor(score)}`;
      bestElement.textContent = `Best: ${bestScore}`;
    }

    function startGame() {
      gameSection.hidden = false;
      resetRun();
      lastTime = performance.now();

      if (animationId !== null) {
        cancelAnimationFrame(animationId);
      }

      animationId = requestAnimationFrame(gameLoop);
      canvas.focus({ preventScroll: true });
    }

    function resetRun() {
      john.y = groundY - john.height;
      john.velocityY = 0;
      john.onGround = true;
      john.stride = 0;
      monster.gap = 132;
      obstacles = [];
      running = true;
      ended = false;
      score = 0;
      speed = 6;
      spawnTimer = 850;
      sceneryOffset = 0;
      stumbleFlash = 0;
      updateScoreboard();
    }

    function jump() {
      if (!running || !john.onGround) {
        return;
      }

      john.velocityY = john.jumpStrength;
      john.onGround = false;
    }

    function spawnObstacle() {
      const roll = Math.random();
      let obstacle;

      if (roll < 0.42) {
        obstacle = { type: "stone", width: 42, height: 34 };
      } else if (roll < 0.78) {
        obstacle = { type: "log", width: 62, height: 30 };
      } else {
        obstacle = { type: "barrier", width: 34, height: 48 };
      }

      obstacle.x = width + 30;
      obstacle.y = groundY - obstacle.height;
      obstacle.hit = false;
      obstacle.passed = false;
      obstacles.push(obstacle);
    }

    function nextSpawnDelay() {
      const difficulty = Math.min(1, score / 1800);
      const minDelay = 760 - difficulty * 180;
      const maxDelay = 1250 - difficulty * 260;
      return minDelay + Math.random() * Math.max(120, maxDelay - minDelay);
    }

    function rectanglesOverlap(a, b) {
      return (
        a.x < b.x + b.width &&
        a.x + a.width > b.x &&
        a.y < b.y + b.height &&
        a.y + a.height > b.y
      );
    }

    function update(delta) {
      const frame = delta / 16.67;
      const currentScore = Math.floor(score);

      score += 0.72 * frame;
      speed = Math.min(12.4, 6 + score / 420);
      sceneryOffset = (sceneryOffset + speed * frame) % width;
      john.stride += 0.22 * frame;
      stumbleFlash = Math.max(0, stumbleFlash - delta);

      john.velocityY += john.gravity * frame;
      john.y += john.velocityY * frame;

      if (john.y >= groundY - john.height) {
        john.y = groundY - john.height;
        john.velocityY = 0;
        john.onGround = true;
      }

      spawnTimer -= delta;
      if (spawnTimer <= 0) {
        spawnObstacle();
        spawnTimer = nextSpawnDelay();
      }

      obstacles.forEach((obstacle) => {
        obstacle.x -= speed * frame;
        if (!obstacle.passed && obstacle.x + obstacle.width < john.x) {
          obstacle.passed = true;
          monster.gap = Math.min(150, monster.gap + 3);
        }
      });
      obstacles = obstacles.filter((obstacle) => obstacle.x + obstacle.width > -40);

      monster.gap -= 0.018 * frame + Math.max(0, speed - 8) * 0.002 * frame;

      const johnHitbox = {
        x: john.x + 7,
        y: john.y + 8,
        width: john.width - 14,
        height: john.height - 10,
      };

      for (const obstacle of obstacles) {
        const obstacleHitbox = {
          x: obstacle.x + 5,
          y: obstacle.y + 5,
          width: obstacle.width - 10,
          height: obstacle.height - 6,
        };

        if (!obstacle.hit && rectanglesOverlap(johnHitbox, obstacleHitbox)) {
          obstacle.hit = true;
          monster.gap -= 36;
          john.velocityY = Math.min(john.velocityY, -5);
          stumbleFlash = 180;
        }
      }

      if (monster.gap <= monster.minGap) {
        endGame();
        return;
      }

      if (Math.floor(score) !== currentScore) {
        updateScoreboard();
      }
    }

    function drawSky() {
      const gradient = ctx.createLinearGradient(0, 0, 0, groundY);
      gradient.addColorStop(0, "#dff7ef");
      gradient.addColorStop(0.62, "#b8e7d0");
      gradient.addColorStop(1, "#86c99b");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, groundY);

      ctx.fillStyle = "rgba(255, 255, 255, 0.76)";
      for (let i = 0; i < 4; i += 1) {
        const cloudX = (i * 255 - sceneryOffset * 0.18 + width) % (width + 180) - 90;
        const cloudY = 42 + (i % 2) * 38;
        ctx.beginPath();
        ctx.arc(cloudX, cloudY, 20, 0, Math.PI * 2);
        ctx.arc(cloudX + 24, cloudY - 7, 24, 0, Math.PI * 2);
        ctx.arc(cloudX + 52, cloudY, 19, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawForest() {
      for (let layer = 0; layer < 2; layer += 1) {
        const spacing = layer === 0 ? 130 : 92;
        const offset = sceneryOffset * (layer === 0 ? 0.34 : 0.58);
        for (let x = -spacing; x < width + spacing; x += spacing) {
          const treeX = x - (offset % spacing);
          const baseY = groundY - (layer === 0 ? 6 : 0);
          ctx.fillStyle = layer === 0 ? "#44725b" : "#2f624b";
          ctx.fillRect(treeX + 18, baseY - 56, 13, 56);
          ctx.fillStyle = layer === 0 ? "#5d9675" : "#367a58";
          ctx.beginPath();
          ctx.moveTo(treeX + 24, baseY - 122);
          ctx.lineTo(treeX - 12, baseY - 48);
          ctx.lineTo(treeX + 60, baseY - 48);
          ctx.closePath();
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(treeX + 24, baseY - 94);
          ctx.lineTo(treeX - 4, baseY - 32);
          ctx.lineTo(treeX + 52, baseY - 32);
          ctx.closePath();
          ctx.fill();
        }
      }
    }

    function drawGround() {
      ctx.fillStyle = "#586b4e";
      ctx.fillRect(0, groundY, width, height - groundY);

      const pathGradient = ctx.createLinearGradient(0, groundY, 0, height);
      pathGradient.addColorStop(0, "#b08968");
      pathGradient.addColorStop(1, "#7f5539");
      ctx.fillStyle = pathGradient;
      ctx.fillRect(0, groundY + 16, width, height - groundY - 16);

      ctx.fillStyle = "rgba(255, 255, 255, 0.26)";
      for (let x = -80; x < width + 120; x += 95) {
        const stripeX = x - (sceneryOffset * 1.28) % 95;
        ctx.fillRect(stripeX, groundY + 53, 48, 5);
      }
    }

    function drawMonster() {
      const monsterX = Math.max(18, john.x - monster.gap - monster.width);
      const monsterY = groundY - monster.height;

      ctx.fillStyle = "rgba(0, 0, 0, 0.25)";
      ctx.beginPath();
      ctx.ellipse(monsterX + 34, groundY + 7, 38, 9, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#050505";
      ctx.beginPath();
      ctx.ellipse(monsterX + 34, monsterY + 38, 31, 39, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(monsterX + 19, monsterY + 19, 14, 0, Math.PI * 2);
      ctx.arc(monsterX + 49, monsterY + 19, 14, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#050505";
      ctx.lineWidth = 8;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(monsterX + 14, monsterY + 52);
      ctx.lineTo(monsterX - 4, monsterY + 70);
      ctx.moveTo(monsterX + 54, monsterY + 52);
      ctx.lineTo(monsterX + 75, monsterY + 66);
      ctx.moveTo(monsterX + 24, monsterY + 73);
      ctx.lineTo(monsterX + 12, monsterY + 84);
      ctx.moveTo(monsterX + 46, monsterY + 73);
      ctx.lineTo(monsterX + 58, monsterY + 84);
      ctx.stroke();

      ctx.fillStyle = "#f8fafc";
      ctx.beginPath();
      ctx.arc(monsterX + 23, monsterY + 32, 4, 0, Math.PI * 2);
      ctx.arc(monsterX + 46, monsterY + 32, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawJohn() {
      const run = john.onGround ? Math.sin(john.stride) : 0.8;
      const hipY = john.y + 41;
      const headX = john.x + 20;

      ctx.fillStyle = "rgba(0, 0, 0, 0.18)";
      ctx.beginPath();
      ctx.ellipse(john.x + 19, groundY + 6, 25, 7, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#16324f";
      ctx.lineWidth = 6;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(john.x + 17, hipY);
      ctx.lineTo(john.x + 8 + run * 7, john.y + 58);
      ctx.moveTo(john.x + 24, hipY);
      ctx.lineTo(john.x + 34 - run * 7, john.y + 58);
      ctx.stroke();

      ctx.strokeStyle = "#236b8e";
      ctx.beginPath();
      ctx.moveTo(john.x + 12, john.y + 26);
      ctx.lineTo(john.x + 3 - run * 5, john.y + 37);
      ctx.moveTo(john.x + 28, john.y + 26);
      ctx.lineTo(john.x + 38 + run * 5, john.y + 34);
      ctx.stroke();

      ctx.fillStyle = "#2a9d8f";
      ctx.fillRect(john.x + 8, john.y + 21, 25, 27);
      ctx.fillStyle = "#f3c38b";
      ctx.beginPath();
      ctx.arc(headX, john.y + 11, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#4a2c1a";
      ctx.fillRect(john.x + 9, john.y + 1, 22, 8);
      ctx.fillStyle = "#172033";
      ctx.beginPath();
      ctx.arc(john.x + 24, john.y + 10, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawObstacles() {
      obstacles.forEach((obstacle) => {
        if (obstacle.type === "stone") {
          ctx.fillStyle = obstacle.hit ? "#cbd5e1" : "#94a3b8";
          ctx.beginPath();
          ctx.moveTo(obstacle.x, obstacle.y + obstacle.height);
          ctx.lineTo(obstacle.x + 10, obstacle.y + 7);
          ctx.lineTo(obstacle.x + 27, obstacle.y);
          ctx.lineTo(obstacle.x + obstacle.width, obstacle.y + obstacle.height);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = "rgba(255, 255, 255, 0.28)";
          ctx.fillRect(obstacle.x + 12, obstacle.y + 10, 12, 5);
        } else if (obstacle.type === "log") {
          ctx.fillStyle = obstacle.hit ? "#a16207" : "#7c2d12";
          ctx.fillRect(obstacle.x, obstacle.y + 7, obstacle.width, obstacle.height - 7);
          ctx.fillStyle = "#b45309";
          ctx.beginPath();
          ctx.ellipse(obstacle.x + 8, obstacle.y + 18, 9, 13, 0, 0, Math.PI * 2);
          ctx.ellipse(
            obstacle.x + obstacle.width - 8,
            obstacle.y + 18,
            9,
            13,
            0,
            0,
            Math.PI * 2
          );
          ctx.fill();
        } else {
          ctx.fillStyle = obstacle.hit ? "#f59e0b" : "#d97706";
          ctx.fillRect(obstacle.x, obstacle.y + 8, obstacle.width, obstacle.height - 8);
          ctx.fillStyle = "#92400e";
          ctx.fillRect(obstacle.x + 6, obstacle.y, 8, obstacle.height);
          ctx.fillRect(obstacle.x + obstacle.width - 14, obstacle.y, 8, obstacle.height);
        }
      });
    }

    function drawHud() {
      ctx.fillStyle = "rgba(255, 255, 255, 0.88)";
      ctx.fillRect(16, 14, 184, 58);
      ctx.fillStyle = "#172033";
      ctx.font = "700 17px Arial";
      ctx.fillText(`Score: ${Math.floor(score)}`, 30, 39);
      ctx.fillText(`Best: ${bestScore}`, 30, 62);

      const danger = Math.max(0, 1 - (monster.gap - monster.minGap) / 118);
      ctx.fillStyle = "#e5e7eb";
      ctx.fillRect(width - 190, 28, 150, 10);
      ctx.fillStyle = danger > 0.65 ? "#c43d3d" : "#1f8f5f";
      ctx.fillRect(width - 190, 28, 150 * danger, 10);
      ctx.fillStyle = "#172033";
      ctx.font = "700 13px Arial";
      ctx.fillText("Monster distance", width - 190, 55);
    }

    function drawScene() {
      ctx.clearRect(0, 0, width, height);
      drawSky();
      drawForest();
      drawGround();
      drawMonster();
      drawObstacles();
      drawJohn();
      drawHud();

      if (stumbleFlash > 0) {
        ctx.fillStyle = `rgba(196, 61, 61, ${Math.min(0.2, stumbleFlash / 900)})`;
        ctx.fillRect(0, 0, width, height);
      }
    }

    function drawIdleScreen() {
      drawScene();
      ctx.fillStyle = "rgba(23, 32, 51, 0.66)";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.font = "700 34px Arial";
      ctx.fillText("Running John", width / 2, height / 2 - 16);
      ctx.font = "18px Arial";
      ctx.fillText("The trail is clear. The chase begins on Play.", width / 2, height / 2 + 24);
      ctx.textAlign = "left";
    }

    function drawGameOver() {
      drawScene();
      ctx.fillStyle = "rgba(23, 32, 51, 0.76)";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.font = "700 40px Arial";
      ctx.fillText("GAME OVER", width / 2, height / 2 - 34);
      ctx.font = "20px Arial";
      ctx.fillText(`Score: ${Math.floor(score)}`, width / 2, height / 2 + 8);
      ctx.fillText(`Best: ${bestScore}`, width / 2, height / 2 + 38);
      ctx.textAlign = "left";
    }

    function endGame() {
      if (ended) {
        return;
      }

      running = false;
      ended = true;
      saveBestScore(score);
      updateScoreboard();
      drawGameOver();

      if (animationId !== null) {
        cancelAnimationFrame(animationId);
        animationId = null;
      }
    }

    function gameLoop(timestamp) {
      if (!running) {
        return;
      }

      const delta = Math.min(40, timestamp - lastTime);
      lastTime = timestamp;
      update(delta);

      if (running) {
        drawScene();
        animationId = requestAnimationFrame(gameLoop);
      }
    }

    startButton.addEventListener("click", startGame);
    restartButton.addEventListener("click", startGame);
    jumpButton.addEventListener("click", jump);
    canvas.addEventListener("pointerdown", jump);

    document.addEventListener("keydown", (event) => {
      if (event.code !== "Space" && event.code !== "ArrowUp") {
        return;
      }

      if (!gameSection.hidden) {
        event.preventDefault();
      }
      jump();
    });
  });
})();
