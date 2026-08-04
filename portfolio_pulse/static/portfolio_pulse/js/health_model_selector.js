document.addEventListener('DOMContentLoaded', () => {
  const select = document.getElementById('id_health_model');
  const dataNode = document.getElementById('pulse-health-model-options');
  const nameNode = document.getElementById('pulse-model-name');
  const kindNode = document.getElementById('pulse-model-kind');
  const descriptionNode = document.getElementById('pulse-model-description');

  if (!select || !dataNode || !nameNode || !kindNode || !descriptionNode) return;

  let models;
  try {
    models = JSON.parse(dataNode.textContent);
  } catch (_error) {
    return;
  }

  const modelsById = Object.fromEntries(models.map((model) => [model.id, model]));
  const form = select.closest('form');
  const sampleMode = form?.dataset.sampleMode === 'true';
  const snapshotInput = document.getElementById('id_snapshot_file');

  const showSelectedDescriptor = () => {
    const model = modelsById[select.value];
    if (!model) return;
    nameNode.textContent = model.name;
    kindNode.textContent = model.kind;
    descriptionNode.textContent = model.short_explainer;
  };

  select.addEventListener('change', showSelectedDescriptor);

  if (sampleMode && snapshotInput && form) {
    snapshotInput.required = false;
    form.addEventListener('submit', (event) => {
      if (snapshotInput.files.length) return;
      event.preventDefault();
      const url = new URL(window.location.href);
      url.searchParams.set('sample', '1');
      url.searchParams.set('health_model', select.value);
      window.location.assign(url.toString());
    });
  }

  showSelectedDescriptor();
});
