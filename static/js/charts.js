document.addEventListener("DOMContentLoaded", () => {
  const canvases = document.querySelectorAll(".mini-chart");

  function parseJson(value, fallback) {
    try {
      return JSON.parse(value || "[]");
    } catch (error) {
      return fallback;
    }
  }

  function cleanSeries(values) {
    return values.map((value) => {
      const number = Number(value);
      return Number.isFinite(number) ? number : 0;
    });
  }

  function drawChart(canvas) {
    const labels = parseJson(canvas.dataset.labels, []);
    const values = cleanSeries(parseJson(canvas.dataset.values, []));
    if (!labels.length || !values.length) {
      return;
    }

    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const padding = 42;
    const color = canvas.dataset.color || "#1f8f5f";
    const unit = canvas.dataset.unit || "";
    const maxValue = Math.max(...values, 1);
    const barGap = 14;
    const barWidth = Math.max(
      8,
      (width - padding * 2 - barGap * (values.length - 1)) / values.length,
    );

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#677085";
    ctx.font = "13px Arial";

    values.forEach((value, index) => {
      const barHeight = Math.round((value / maxValue) * (height - padding * 2));
      const x = padding + index * (barWidth + barGap);
      const y = height - padding - barHeight;

      ctx.fillStyle = color;
      ctx.fillRect(x, y, barWidth, Math.max(1, barHeight));
      ctx.fillStyle = "#677085";
      ctx.fillText(String(labels[index] || ""), x, height - 14);
      ctx.fillStyle = "#172033";
      ctx.fillText(`${value}${unit ? ` ${unit}` : ""}`, x, Math.max(18, y - 8));
    });
  }

  canvases.forEach(drawChart);
});
