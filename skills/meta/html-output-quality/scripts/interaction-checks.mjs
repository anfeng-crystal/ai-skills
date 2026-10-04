// An action must change observable report state; focus and an input value alone
// demonstrate operability but do not demonstrate working report interaction.
async function snapshot(page) {
  return page.evaluate(() => {
    function visible(node) {
      if (!node.getClientRects().length) return false;
      for (let current = node; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility)) return false;
      }
      return true;
    }
    return JSON.stringify({
      rows: [...document.querySelectorAll('tbody tr')].filter(visible).map((row) => row.innerText),
      panels: [...document.querySelectorAll('[data-panel]')].filter(visible).map((panel) => panel.getAttribute('data-panel')),
      text: document.body?.innerText || '',
      sorts: [...document.querySelectorAll('th[data-sort]')].filter(visible).map((node) => node.getAttribute('aria-sort')),
      details: [...document.querySelectorAll('details')].filter(visible).map((node) => node.open),
    });
  });
}

async function firstUsable(page, selector, skip = 0) {
  const matches = page.locator(selector);
  for (let index = skip; index < await matches.count(); index += 1) {
    const candidate = matches.nth(index);
    if (await candidate.isVisible() && await candidate.isEnabled()) return candidate;
  }
  return null;
}

async function changedAfter(page, before) {
  // Cover common short debounces without turning this smoke check into a full UI test.
  const deadline = Date.now() + 1000;
  do {
    if (await snapshot(page) !== before) return true;
    await page.waitForTimeout(50);
  } while (Date.now() < deadline);
  return false;
}

export async function smokeTestInteraction(page) {
  const actions = [
    { name: 'search', selector: 'input[type="search"], input:not([type])' },
    { name: 'filter-card', selector: 'button[data-filter-level]', skip: 1 },
    { name: 'tab', selector: 'button[data-tab]', skip: 1 },
    { name: 'sort', selector: 'th[data-sort]' },
    { name: 'details', selector: 'summary' },
    { name: 'button', selector: 'button' },
  ];
  for (const action of actions) {
    const target = await firstUsable(page, action.selector, action.skip);
    if (!target) continue;
    const before = await snapshot(page);
    if (action.name === 'search') {
      const original = await target.inputValue();
      await target.fill('__html_gate_no_match__', { timeout: 1500 });
      if (await changedAfter(page, before)) return { ok: true, action: action.name };
      await target.fill(original, { timeout: 1500 });
    } else {
      await target.click({ timeout: 1500 });
      if (await changedAfter(page, before)) return { ok: true, action: action.name };
    }
  }
  return { ok: false, reason: 'no supported interaction changed visible state' };
}
