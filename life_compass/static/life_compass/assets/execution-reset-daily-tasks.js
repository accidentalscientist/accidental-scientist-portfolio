function todayKey() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `lifeCompass.dailyTasks.${year}-${month}-${day}`;
}

function emptyTaskSlots() {
  return Array.from({ length: 3 }, () => ({
    text: "",
    done: false,
    projectId: null,
    subtaskId: null,
  }));
}

function dailyTasks() {
  try {
    const tasks = JSON.parse(localStorage.getItem(todayKey()) || "[]");
    return Array.isArray(tasks) ? tasks : [];
  } catch {
    return [];
  }
}

function allThreeTasksAreComplete() {
  const tasks = dailyTasks();
  return tasks.length === 3 && tasks.every((task) => task?.text?.trim() && task.done === true);
}

function updateResetAvailability() {
  const resetButton = document.getElementById("reset-day");
  const resetWrap = document.getElementById("reset-day-wrap");
  if (!resetButton) return;

  const canClear = allThreeTasksAreComplete();
  resetButton.disabled = !canClear;
  resetWrap?.classList.toggle("is-locked", !canClear);
}

function confirmClear() {
  const dialog = document.getElementById("confirm-modal");
  if (!dialog) {
    return Promise.resolve(window.confirm("Clear today's three task slots? Completed tasks will stay completed."));
  }

  const message = document.getElementById("confirm-message");
  const confirmButton = document.getElementById("confirm-ok");
  const cancelButton = document.getElementById("confirm-cancel");
  message.textContent = "Clear today's three task slots? Completed tasks will stay completed.";
  confirmButton.textContent = "Clear";

  return new Promise((resolve) => {
    const finish = (confirmed) => {
      confirmButton.removeEventListener("click", accept);
      cancelButton.removeEventListener("click", cancel);
      dialog.removeEventListener("cancel", cancel);
      dialog.close();
      resolve(confirmed);
    };
    const accept = () => finish(true);
    const cancel = () => finish(false);

    confirmButton.addEventListener("click", accept);
    cancelButton.addEventListener("click", cancel);
    dialog.addEventListener("cancel", cancel);
    dialog.showModal();
  });
}

document.getElementById("reset-day")?.addEventListener("click", async () => {
  if (!allThreeTasksAreComplete()) return;
  if (!(await confirmClear())) return;

  // Only replace the three display slots. Project subtasks, ledger entries,
  // and the earned calendar mark live under separate keys and remain intact.
  localStorage.setItem(todayKey(), JSON.stringify(emptyTaskSlots()));
  window.location.reload();
});

const dailyTaskList = document.getElementById("daily-task-list");
if (dailyTaskList) {
  new MutationObserver(updateResetAvailability).observe(dailyTaskList, {
    childList: true,
    subtree: true,
  });
}
updateResetAvailability();
