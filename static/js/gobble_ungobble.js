(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const gameSection = document.querySelector("#gobble-ungobble-game");
    const startButton = document.querySelector("#start-gobble-ungobble");
    const restartButton = document.querySelector("#restart-gobble-ungobble");
    const leftButton = document.querySelector("#gobble-left");
    const rightButton = document.querySelector("#gobble-right");
    const canvas = document.querySelector("#gobble-ungobble-canvas");
    const scoreElement = document.querySelector("#gobble-ungobble-score");
    const bestElement = document.querySelector("#gobble-ungobble-best");
    const livesElement = document.querySelector("#gobble-ungobble-lives");

    if (
      !gameSection ||
      !startButton ||
      !restartButton ||
      !leftButton ||
      !rightButton ||
      !canvas ||
      !scoreElement ||
      !bestElement ||
      !livesElement
    ) {
      return;
    }

    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const storageKey = "fitnessTrackerGobbleUngobbleBest";
    const healthyItems = ["apple", "banana", "watermelon", "water"];
    const junkItems = ["candy", "chips", "donut", "soda"];

    let animationId = null;
    let lastTime = 0;
    let running = false;
    let ended = false;
    let score = 0;
    let bestScore = readBestScore();
    let lives = 3;
    let spawnTimer = 0;
    let items = [];
    let feedbacks = [];
    let wrongFlash = 0;
    let keys = { left: false, right: false };
    let holdDirection = 0;

    const player = {
      x: width / 2 - 42,
      y: height - 64,
      width: 84,
      height: 36,
      speed: 430,
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
      scoreElement.textContent = `Score: ${score}`;
      bestElement.textContent = `Best: ${bestScore}`;
      livesElement.textContent = `Lives: ${lives}`;
    }

    function resetGame() {
      running = true;
      ended = false;
      score = 0;
      lives = 3;
      spawnTimer = 600;
      items = [];
      feedbacks = [];
      wrongFlash = 0;
      keys = { left: false, right: false };
      holdDirection = 0;
      player.x = width / 2 - player.width / 2;
      updateScoreboard();
    }

    function startGame() {
      gameSection.hidden = false;
      resetGame();
      lastTime = performance.now();

      if (animationId !== null) {
        cancelAnimationFrame(animationId);
      }

      animationId = requestAnimationFrame(gameLoop);
      canvas.focus({ preventScroll: true });
    }

    function difficultyLevel() {
      return Math.min(7, Math.floor(Math.max(0, score) / 60));
    }

    function spawnDelay() {
      const level = difficultyLevel();
      return Math.max(320, 900 - level * 75 + Math.random() * 180);
    }

    function spawnItem() {
      const healthy = Math.random() > Math.min(0.46, 0.28 + difficultyLevel() * 0.025);
      const names = healthy ? healthyItems : junkItems;
      const kind = names[Math.floor(Math.random() * names.length)];
      const size = healthy ? 34 + Math.random() * 8 : 36 + Math.random() * 10;
      const level = difficultyLevel();

      items.push({
        x: 30 + Math.random() * (width - 60),
        y: -size - 12,
        radius: size / 2,
        healthy,
        kind,
        speed: 112 + level * 24 + Math.random() * 45,
        wobble: Math.random() * Math.PI * 2,
        drift: (Math.random() - 0.5) * (36 + level * 6),
      });

      if (level >= 4 && Math.random() < 0.2) {
        items.push({
          x: 30 + Math.random() * (width - 60),
          y: -size - 70,
          radius: size / 2,
          healthy: Math.random() > 0.45,
          kind: Math.random() > 0.45 ? "apple" : "chips",
          speed: 124 + level * 25 + Math.random() * 50,
          wobble: Math.random() * Math.PI * 2,
          drift: (Math.random() - 0.5) * (42 + level * 5),
        });
      }
    }

    function clamp(value, min, max) {
      return Math.min(max, Math.max(min, value));
    }

    function addFeedback(text, x, y, color) {
      feedbacks.push({
        text,
        x,
        y,
        color,
        life: 720,
      });
    }

    function rectanglesOverlapCircle(rect, circle) {
      const nearestX = clamp(circle.x, rect.x, rect.x + rect.width);
      const nearestY = clamp(circle.y, rect.y, rect.y + rect.height);
      const dx = circle.x - nearestX;
      const dy = circle.y - nearestY;
      return dx * dx + dy * dy <= circle.radius * circle.radius;
    }

    function applyItemResult(item) {
      if (item.healthy) {
        score += 10;
        addFeedback("+10", item.x, item.y, "#1f8f5f");
      } else {
        score -= 10;
        lives -= 1;
        wrongFlash = 260;
        addFeedback("-10", item.x, item.y, "#c43d3d");
      }

      if (score > bestScore) {
        saveBestScore(score);
      }

      updateScoreboard();
      if (lives <= 0) {
        endGame();
      }
    }

    function missHealthyItem(item) {
      lives -= 1;
      wrongFlash = 210;
      addFeedback("Missed good", item.x, height - 54, "#c43d3d");
      updateScoreboard();
      if (lives <= 0) {
        endGame();
      }
    }

    function update(delta) {
      const seconds = delta / 1000;
      const move =
        (keys.right ? 1 : 0) -
        (keys.left ? 1 : 0) +
        holdDirection;

      if (move !== 0) {
        player.x = clamp(
          player.x + Math.sign(move) * player.speed * seconds,
          12,
          width - player.width - 12
        );
      }

      spawnTimer -= delta;
      if (spawnTimer <= 0) {
        spawnItem();
        spawnTimer = spawnDelay();
      }

      wrongFlash = Math.max(0, wrongFlash - delta);

      items.forEach((item) => {
        item.y += item.speed * seconds;
        item.wobble += seconds * 3;
        item.x += Math.sin(item.wobble) * item.drift * seconds;
        item.x = clamp(item.x, item.radius + 8, width - item.radius - 8);
      });

      const playerRect = {
        x: player.x,
        y: player.y - 7,
        width: player.width,
        height: player.height + 10,
      };

      const remaining = [];
      for (const item of items) {
        if (rectanglesOverlapCircle(playerRect, item)) {
          applyItemResult(item);
        } else if (item.y - item.radius > height) {
          if (item.healthy) {
            missHealthyItem(item);
          }
        } else {
          remaining.push(item);
        }
      }
      items = remaining;

      feedbacks = feedbacks
        .map((feedback) => ({
          ...feedback,
          y: feedback.y - 34 * seconds,
          life: feedback.life - delta,
        }))
        .filter((feedback) => feedback.life > 0);
    }

    function drawBackground() {
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, "#eef8ff");
      gradient.addColorStop(0.58, "#f7fbf8");
      gradient.addColorStop(1, "#ddebdc");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      ctx.fillStyle = "#d9eadb";
      ctx.fillRect(0, height - 86, width, 86);
      ctx.fillStyle = "#edf7ee";
      for (let x = -40; x < width + 40; x += 62) {
        ctx.beginPath();
        ctx.ellipse(x, height - 48, 28, 7, -0.18, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawPlayer() {
      const x = player.x;
      const y = player.y;

      ctx.fillStyle = "rgba(0, 0, 0, 0.14)";
      ctx.beginPath();
      ctx.ellipse(x + player.width / 2, y + 33, 48, 9, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#2563eb";
      ctx.beginPath();
      ctx.moveTo(x + 4, y + 5);
      ctx.quadraticCurveTo(x + player.width / 2, y + 48, x + player.width - 4, y + 5);
      ctx.lineTo(x + player.width - 12, y + 32);
      ctx.quadraticCurveTo(x + player.width / 2, y + 55, x + 12, y + 32);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = "#1d4ed8";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.moveTo(x + 8, y + 7);
      ctx.quadraticCurveTo(x + player.width / 2, y + 28, x + player.width - 8, y + 7);
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(x + 28, y + 18, 4, 0, Math.PI * 2);
      ctx.arc(x + 56, y + 18, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawApple(item) {
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      ctx.arc(item.x, item.y + 3, item.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#22c55e";
      ctx.beginPath();
      ctx.ellipse(item.x + 10, item.y - item.radius + 4, 10, 5, -0.5, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawBanana(item) {
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = item.radius * 0.72;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.arc(item.x - 2, item.y - 4, item.radius * 1.16, 0.2, 2.4);
      ctx.stroke();
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(item.x - 2, item.y - 4, item.radius * 1.16, 0.2, 2.4);
      ctx.stroke();
    }

    function drawWatermelon(item) {
      ctx.fillStyle = "#16a34a";
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.radius, Math.PI, 0);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#fb7185";
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.radius - 5, Math.PI, 0);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#172033";
      for (let i = -1; i <= 1; i += 1) {
        ctx.beginPath();
        ctx.arc(item.x + i * 10, item.y - 8, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawWater(item) {
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.moveTo(item.x, item.y - item.radius);
      ctx.quadraticCurveTo(item.x + item.radius, item.y, item.x, item.y + item.radius);
      ctx.quadraticCurveTo(item.x - item.radius, item.y, item.x, item.y - item.radius);
      ctx.fill();
      ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
      ctx.beginPath();
      ctx.arc(item.x - 6, item.y - 2, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawCandy(item) {
      ctx.fillStyle = "#ec4899";
      ctx.fillRect(item.x - item.radius, item.y - 10, item.radius * 2, 20);
      ctx.fillStyle = "#f9a8d4";
      ctx.beginPath();
      ctx.moveTo(item.x - item.radius, item.y);
      ctx.lineTo(item.x - item.radius - 14, item.y - 12);
      ctx.lineTo(item.x - item.radius - 14, item.y + 12);
      ctx.closePath();
      ctx.moveTo(item.x + item.radius, item.y);
      ctx.lineTo(item.x + item.radius + 14, item.y - 12);
      ctx.lineTo(item.x + item.radius + 14, item.y + 12);
      ctx.closePath();
      ctx.fill();
    }

    function drawChips(item) {
      ctx.fillStyle = "#f97316";
      ctx.fillRect(item.x - item.radius * 0.82, item.y - item.radius, item.radius * 1.64, item.radius * 2);
      ctx.fillStyle = "#fde68a";
      ctx.fillRect(item.x - item.radius * 0.48, item.y - 7, item.radius * 0.96, 14);
      ctx.fillStyle = "#9a3412";
      ctx.font = "700 12px Arial";
      ctx.textAlign = "center";
      ctx.fillText("CHIP", item.x, item.y + 4);
      ctx.textAlign = "left";
    }

    function drawDonut(item) {
      ctx.fillStyle = "#a16207";
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#f9a8d4";
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.radius * 0.72, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#eef8ff";
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.radius * 0.32, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawSoda(item) {
      ctx.fillStyle = "#dc2626";
      ctx.fillRect(item.x - item.radius * 0.55, item.y - item.radius, item.radius * 1.1, item.radius * 2);
      ctx.fillStyle = "#fee2e2";
      ctx.fillRect(item.x - item.radius * 0.35, item.y - 8, item.radius * 0.7, 16);
      ctx.fillStyle = "#ffffff";
      ctx.font = "700 11px Arial";
      ctx.textAlign = "center";
      ctx.fillText("SODA", item.x, item.y + 4);
      ctx.textAlign = "left";
    }

    function drawItem(item) {
      ctx.save();
      ctx.translate(item.x, item.y);
      ctx.rotate(Math.sin(item.wobble) * 0.1);
      ctx.translate(-item.x, -item.y);

      if (item.kind === "apple") {
        drawApple(item);
      } else if (item.kind === "banana") {
        drawBanana(item);
      } else if (item.kind === "watermelon") {
        drawWatermelon(item);
      } else if (item.kind === "water") {
        drawWater(item);
      } else if (item.kind === "candy") {
        drawCandy(item);
      } else if (item.kind === "chips") {
        drawChips(item);
      } else if (item.kind === "donut") {
        drawDonut(item);
      } else {
        drawSoda(item);
      }

      ctx.restore();
    }

    function drawFeedback() {
      feedbacks.forEach((feedback) => {
        ctx.globalAlpha = Math.max(0, Math.min(1, feedback.life / 400));
        ctx.fillStyle = feedback.color;
        ctx.font = "700 20px Arial";
        ctx.textAlign = "center";
        ctx.fillText(feedback.text, feedback.x, feedback.y);
      });
      ctx.globalAlpha = 1;
      ctx.textAlign = "left";
    }

    function drawHud() {
      ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
      ctx.fillRect(16, 14, 238, 76);
      ctx.fillStyle = "#172033";
      ctx.font = "700 17px Arial";
      ctx.fillText(`Score: ${score}`, 30, 39);
      ctx.fillText(`Best: ${bestScore}`, 30, 63);
      ctx.fillStyle = lives <= 1 ? "#c43d3d" : "#1f8f5f";
      ctx.fillText(`Lives: ${lives}`, 148, 39);
    }

    function drawScene() {
      ctx.clearRect(0, 0, width, height);
      drawBackground();
      items.forEach(drawItem);
      drawPlayer();
      drawFeedback();
      drawHud();

      if (wrongFlash > 0) {
        ctx.fillStyle = `rgba(196, 61, 61, ${Math.min(0.24, wrongFlash / 850)})`;
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
      ctx.fillText("Gobble & Ungobble", width / 2, height / 2 - 18);
      ctx.font = "18px Arial";
      ctx.fillText("Fresh food is falling. The round starts on Play.", width / 2, height / 2 + 24);
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
      ctx.fillText(`Score: ${score}`, width / 2, height / 2 + 8);
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

    function movePlayerToClientX(clientX) {
      const rect = canvas.getBoundingClientRect();
      const scale = width / rect.width;
      const x = (clientX - rect.left) * scale;
      player.x = clamp(x - player.width / 2, 12, width - player.width - 12);
    }

    startButton.addEventListener("click", startGame);
    restartButton.addEventListener("click", startGame);

    leftButton.addEventListener("pointerdown", () => {
      holdDirection = -1;
    });
    rightButton.addEventListener("pointerdown", () => {
      holdDirection = 1;
    });
    document.addEventListener("pointerup", () => {
      holdDirection = 0;
    });

    canvas.addEventListener("pointerdown", (event) => {
      if (!running) {
        return;
      }
      movePlayerToClientX(event.clientX);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!running || event.buttons === 0) {
        return;
      }
      movePlayerToClientX(event.clientX);
    });

    document.addEventListener("keydown", (event) => {
      if (gameSection.hidden) {
        return;
      }

      if (event.code === "ArrowLeft" || event.code === "KeyA") {
        keys.left = true;
        event.preventDefault();
      } else if (event.code === "ArrowRight" || event.code === "KeyD") {
        keys.right = true;
        event.preventDefault();
      }
    });

    document.addEventListener("keyup", (event) => {
      if (event.code === "ArrowLeft" || event.code === "KeyA") {
        keys.left = false;
      } else if (event.code === "ArrowRight" || event.code === "KeyD") {
        keys.right = false;
      }
    });
  });
})();
