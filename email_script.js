const emailsTextarea = document.getElementById("emails");
const subjectTextarea = document.getElementById("subject");
const bodyTextarea = document.getElementById("body");
const attachmentInput = document.getElementById("attachment");
const apiTokenTextarea = document.getElementById("apiToken");

const sendBtn = document.getElementById("sendBtn");
const pauseBtn = document.getElementById("pauseBtn");
const stopBtn = document.getElementById("stopBtn");
const viewHistoryBtn = document.getElementById("viewHistoryBtn");

const statusLog = document.getElementById("statusLog");
const emailCountSpan = document.getElementById("emailCount");

let campaignId = null;
let pollingInterval = null;

function updateEmailCount() {
  const lines = emailsTextarea.value
    .split("\n")
    .map(line => line.trim())
    .filter(line => line && line.includes("@"));
  emailCountSpan.textContent = `${lines.length} emails`;
}

emailsTextarea.addEventListener("input", updateEmailCount);

function logStatus(text) {
  statusLog.textContent += text + "\n";
  statusLog.scrollTop = statusLog.scrollHeight;
}

function setButtonsOnSendStart() {
  sendBtn.disabled = true;
  pauseBtn.disabled = false;
  stopBtn.disabled = false;
}

function resetButtons() {
  sendBtn.disabled = false;
  pauseBtn.disabled = true;
  stopBtn.disabled = true;
}

async function startCampaign() {
  if (!emailsTextarea.value.trim()) {
    alert("Please enter at least one email.");
    return;
  }
  if (!apiTokenTextarea.value.trim()) {
    alert("Please paste your Gmail API client secret JSON.");
    return;
  }

  const formData = new FormData();
  formData.append("emails", emailsTextarea.value.trim());
  formData.append("subject", subjectTextarea.value.trim());
  formData.append("body", bodyTextarea.value);
  formData.append("clientSecret", apiTokenTextarea.value.trim());

  if (attachmentInput.files.length > 0) {
    formData.append("attachment", attachmentInput.files[0]);
  }

  logStatus("Starting campaign...");

  try {
    const response = await fetch("/start-campaign", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (data.error) {
      alert("Error: " + data.error);
      logStatus("Error: " + data.error);
      return;
    }

    campaignId = data.campaign_id;
    logStatus(`Campaign started. Opening Gmail authorization...`);
    setButtonsOnSendStart();

    // Open Gmail OAuth in new tab
    window.open(data.auth_url, "_blank");

    // Start polling status
    startPolling();

  } catch (e) {
    alert("Network or server error.");
    logStatus("Network or server error.");
  }
}

async function fetchStatus() {
  if (!campaignId) return;

  try {
    const response = await fetch(`/status/${campaignId}`);
    const data = await response.json();

    if (data.error) {
      logStatus("Status error: " + data.error);
      stopPolling();
      resetButtons();
      return;
    }

    // Update log
    statusLog.textContent = data.log.join("\n");

    if (data.progress >= data.emails_count) {
      logStatus("✅ All emails sent.");
      stopPolling();
      resetButtons();
    }

    if (data.stopped) {
      logStatus("⛔ Sending stopped.");
      stopPolling();
      resetButtons();
    }

  } catch (e) {
    logStatus("Failed to fetch status.");
  }
}

function startPolling() {
  if (pollingInterval) clearInterval(pollingInterval);
  pollingInterval = setInterval(fetchStatus, 3000);
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
}

async function pauseSending() {
  if (!campaignId) return;
  try {
    await fetch(`/pause/${campaignId}`, { method: "POST" });
    logStatus("⏸️ Paused sending.");
    pauseBtn.disabled = true;
    sendBtn.disabled = false;
  } catch (e) {
    logStatus("Failed to pause.");
  }
}

async function resumeSending() {
  if (!campaignId) return;
  try {
    await fetch(`/resume/${campaignId}`, { method: "POST" });
    logStatus("▶️ Resumed sending.");
    pauseBtn.disabled = false;
    sendBtn.disabled = true;
  } catch (e) {
    logStatus("Failed to resume.");
  }
}

async function stopSending() {
  if (!campaignId) return;
  try {
    await fetch(`/stop/${campaignId}`, { method: "POST" });
    logStatus("⛔ Stopping sending...");
    stopBtn.disabled = true;
    pauseBtn.disabled = true;
    sendBtn.disabled = false;
  } catch (e) {
    logStatus("Failed to stop.");
  }
}

// Button event listeners
sendBtn.addEventListener("click", () => {
  if (pauseBtn.disabled) {
    startCampaign();
  } else {
    // If paused, resume sending
    resumeSending();
  }
});

pauseBtn.addEventListener("click", () => {
  pauseSending();
});

stopBtn.addEventListener("click", () => {
  stopSending();
});

viewHistoryBtn.addEventListener("click", () => {
  window.location.href = "history.html";
});

// Initialize email count on load
updateEmailCount();
