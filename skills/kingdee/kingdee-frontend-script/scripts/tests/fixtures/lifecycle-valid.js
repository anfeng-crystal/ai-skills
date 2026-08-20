export var handler = null;
export var timerId = null;

export function didMount() {
  handler = (event) => {
    if (!['https://example.invalid'].includes(event.origin)) return;
  };
  window.addEventListener('message', handler);
  timerId = setInterval(() => {}, 1000);
}

export function willUnmount() {
  window.removeEventListener('message', handler);
  clearInterval(timerId);
}
