export interface KeyLease {
  value: string;
  index: number;
  provider: string;
}

interface KeyState {
  disabledReason?: string;
  disabledUntil?: number;
  cooldownUntil?: number;
}

export class KeyPool {
  private cursor = 0;
  private readonly states: KeyState[];

  constructor(
    private readonly provider: string,
    private readonly keys: string[],
    private readonly now: () => number = () => Date.now(),
  ) {
    this.states = keys.map(() => ({}));
  }

  get size(): number {
    return this.keys.length;
  }

  next(): KeyLease | undefined {
    if (this.keys.length === 0) {
      return undefined;
    }
    for (let attempt = 0; attempt < this.keys.length; attempt += 1) {
      const index = this.cursor % this.keys.length;
      this.cursor = (index + 1) % this.keys.length;
      const state = this.states[index];
      this.recoverExpiredState(state);
      if (state.disabledReason) {
        continue;
      }
      if (state.cooldownUntil && state.cooldownUntil > this.now()) {
        continue;
      }
      return { value: this.keys[index], index, provider: this.provider };
    }
    return undefined;
  }

  cooldown(lease: KeyLease, retryAfterMs: number): void {
    this.states[lease.index].cooldownUntil = this.now() + Math.max(0, retryAfterMs);
  }

  disable(lease: KeyLease, reason: string, disabledUntil = nextMonthStart(this.now())): void {
    this.states[lease.index].disabledReason = reason;
    this.states[lease.index].disabledUntil = disabledUntil;
  }

  status(): { keyCount: number; cooldownCount: number; disabledCount: number } {
    const now = this.now();
    for (const state of this.states) {
      this.recoverExpiredState(state);
    }
    return {
      keyCount: this.keys.length,
      cooldownCount: this.states.filter((state) => state.cooldownUntil && state.cooldownUntil > now).length,
      disabledCount: this.states.filter((state) => state.disabledReason).length,
    };
  }

  private recoverExpiredState(state: KeyState): void {
    const now = this.now();
    if (state.disabledReason && state.disabledUntil !== undefined && state.disabledUntil <= now) {
      delete state.disabledReason;
      delete state.disabledUntil;
    }
    if (state.cooldownUntil !== undefined && state.cooldownUntil <= now) {
      delete state.cooldownUntil;
    }
  }
}

function nextMonthStart(now: number): number {
  const date = new Date(now);
  return new Date(date.getFullYear(), date.getMonth() + 1, 1).getTime();
}
