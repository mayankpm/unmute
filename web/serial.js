export class BedsideController extends EventTarget {
  constructor() {
    super();
    this.port = null;
    this.reader = null;
    this.writer = null;
    this.chain = Promise.resolve();
  }
  get connected() { return !!this.writer; }
  async connect(known = null) {
    if (!('serial' in navigator)) throw new Error('USB controls need desktop Chrome or Edge.');
    if (this.port) return;
    if (!known) this.manualDisconnect = false;
    // `known` is a port this site was already allowed to use: reconnect without the picker.
    const port = known || await navigator.serial.requestPort();
    try {
      await port.open({baudRate: 115200});
      this.port = port;
      this.writer = port.writable.getWriter();
      this.dispatchEvent(new Event('connected'));
      this.readLoop();
    } catch (error) {
      this.port = null;
      throw error;
    }
  }
  async readLoop() {
    let buffer = '';
    const decoder = new TextDecoder();
    this.reader = this.port.readable.getReader();
    try {
      while (true) {
        const {value, done} = await this.reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let end;
        while ((end = buffer.indexOf('\n')) !== -1) {
          const line = buffer.slice(0, end).trim();
          buffer = buffer.slice(end + 1);
          if (line) this.dispatchEvent(new CustomEvent('command', {detail: line}));
        }
        if (buffer.length > 512) buffer = '';
      }
    } catch (error) {
      this.dispatchEvent(new CustomEvent('error', {detail: error.message}));
    } finally {
      this.reader.releaseLock();
      this.reader = null;
      if (this.writer) { this.writer.releaseLock(); this.writer = null; }
      try { await this.port?.close(); } catch { /* disconnected device */ }
      this.port = null;
      this.dispatchEvent(new Event('disconnected'));
    }
  }
  send(state, text = '') {
    const safeText = text.replace(/[^\x20-\x7e]/g, ' ').replace(/\|/g, ' ').slice(0, 60);
    this.chain = this.chain.catch(() => {}).then(async () => {
      if (this.writer) await this.writer.write(new TextEncoder().encode(`STATE|${state}|${safeText}\n`));
    });
    return this.chain;
  }
  async disconnect() {
    this.manualDisconnect = true;
    if (this.reader) await this.reader.cancel();
  }
  // Reconnect to the previously approved board after a page reload, and when it is plugged back in.
  autoReconnect() {
    // Best effort only: it must never stop the rest of the app from starting.
    const serial = navigator.serial;
    if (!serial || typeof serial.getPorts !== 'function') return;
    const tryKnown = async () => {
      try {
        if (this.port || this.manualDisconnect) return;
        const [port] = await serial.getPorts();
        if (port) await this.connect(port);
      } catch { /* the board stays available through the Connect button */ }
    };
    if (typeof serial.addEventListener === 'function') serial.addEventListener('connect', tryKnown);
    tryKnown();
  }
}
