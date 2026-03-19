document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.card-premium, .hero-card, .feature-card, .auth-shell, .kpi-card, .fade-enter');
  cards.forEach((el, idx) => {
    el.classList.add('fade-enter');
    setTimeout(() => {
      el.classList.add('show');
    }, idx * 40);
  });
});
