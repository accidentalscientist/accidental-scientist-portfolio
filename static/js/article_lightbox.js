document.addEventListener('DOMContentLoaded', function () {
  var dialog = document.getElementById('article-image-lightbox');
  var expandedImage = document.getElementById('article-image-lightbox-image');
  var caption = document.getElementById('article-image-lightbox-caption');
  var closeButton = dialog && dialog.querySelector('.article-image-lightbox__close');

  if (!dialog || !expandedImage || !caption || !closeButton) return;

  document.querySelectorAll('.article-image-trigger').forEach(function (trigger) {
    trigger.addEventListener('click', function () {
      var sourceImage = trigger.querySelector('img');
      if (!sourceImage) return;

      expandedImage.src = sourceImage.currentSrc || sourceImage.src;
      expandedImage.alt = sourceImage.alt || '';
      caption.textContent = sourceImage.alt || 'Article image';
      dialog.showModal();
    });
  });

  closeButton.addEventListener('click', function () {
    dialog.close();
  });

  dialog.addEventListener('click', function (event) {
    if (event.target === dialog) dialog.close();
  });

  dialog.addEventListener('close', function () {
    expandedImage.removeAttribute('src');
    expandedImage.alt = '';
    caption.textContent = '';
  });
});
