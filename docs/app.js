/* global Chart */

function $(sel) {
  return document.querySelector(sel);
}

function showTab(tabName) {
  const chartTab = $("#tab-chart");
  const sheetTab = $("#tab-sheet");
  const chartPanel = $("#panel-chart");
  const sheetPanel = $("#panel-sheet");

  const isChart = tabName === "chart";

  chartTab.classList.toggle("is-active", isChart);
  sheetTab.classList.toggle("is-active", !isChart);

  chartTab.setAttribute("aria-selected", isChart ? "true" : "false");
  sheetTab.setAttribute("aria-selected", !isChart ? "true" : "false");

  chartPanel.classList.toggle("is-active", isChart);
  sheetPanel.classList.toggle("is-active", !isChart);

  chartPanel.hidden = !isChart;
  sheetPanel.hidden = isChart;
}

function parseCSV(text) {
  // Minimal CSV parser: good enough for this dataset.
  const lines = text.trim().split(/\r?\n/);
  const headers = lines[0].split(",").map(s => s.trim());
  const out = [];

  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    const row = {};
    for (let j = 0; j < headers.length; j++) {
      const key = headers[j];
      const raw = (parts[j] ?? "").trim();
      const num = raw === "" ? null : Number(raw);
      row[key] = Number.isFinite(num) ? num : raw;
    }
    out.push(row);
  }

  return out;
}

function toLabel(year, month) {
  const y = String(year).padStart(4, "0");
  const m = String(month).padStart(2, "0");
  return `${y}-${m}`;
}

async function loadData() {
  const res = await fetch("./data/tiobe-perl.csv", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load data: ${res.status} ${res.statusText}`);
  }
  const text = await res.text();
  return parseCSV(text);
}

function buildChart(rows) {
  const labels = rows.map(r => toLabel(r.Year, r.Month));
  const positions = rows.map(r => r.Position);

  const latest = rows[rows.length - 1];
  const meta = $("#chart-meta");
  if (latest) {
    meta.textContent = `Latest: ${toLabel(latest.Year, latest.Month)} — position ${latest.Position}.`;
  }

  const ctx = $("#tiobeChart");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "TIOBE position (lower is better)",
          data: positions,
          tension: 0.2,
          pointRadius: 0,
          borderWidth: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `Position: ${ctx.parsed.y}`
          }
        }
      },
      scales: {
        y: {
          reverse: true,
          title: {
            display: true,
            text: "Position (1 is best)"
          },
          ticks: {
            precision: 0
          }
        },
        x: {
          title: {
            display: true,
            text: "Year-Month"
          },
          ticks: {
            maxTicksLimit: 12
          }
        }
      }
    }
  });
}

function initTabs() {
  $("#tab-chart").addEventListener("click", () => showTab("chart"));
  $("#tab-sheet").addEventListener("click", () => showTab("sheet"));
}

async function main() {
  initTabs();

  try {
    const rows = await loadData();
    buildChart(rows);
  } catch (err) {
    console.error(err);
    const meta = $("#chart-meta");
    meta.textContent = "Couldn’t load the CSV data. Check the console for details.";
  }
}

document.addEventListener("DOMContentLoaded", main);
