// Phone Menu button for the top bar. The CSS only collapses the links once `is-js` is set, so without
// JavaScript they stay visible. Behaviour is covered by tests/nav.test.js.
(() => {
  const nav = document.querySelector('.nav');
  const button = nav && nav.querySelector('.nav__toggle');
  if (!button) return;

  const setOpen = open => {
    nav.classList.toggle('is-open', open);
    button.setAttribute('aria-expanded', String(open));
  };

  nav.classList.add('is-js');
  button.hidden = false;
  button.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
  nav.addEventListener('keydown', event => {
    if (event.key === 'Escape' && nav.classList.contains('is-open')) {
      setOpen(false);
      button.focus();
    }
  });
})();
