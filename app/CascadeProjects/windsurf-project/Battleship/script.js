class BattleshipGame {
     constructor() {
         // Board + ships
         this.boardSize = 10;
         this.shipTypes = [
             { name: 'Carrier', size: 5 },
             { name: 'Battleship', size: 4 },
             { name: 'Cruiser', size: 3 },
             { name: 'Submarine', size: 3 },
             { name: 'Destroyer', size: 2 }
         ];

         // UI / turn
        this.phase = 'setup'; // setup | player_turn | ai_turn | game_over
        this.shipOrientation = 'horizontal';
        this.selectedShipId = null;

        // Difficulty
        this.difficulty = 'medium'; // easy | medium | hard

        // Move logs (keep last 5)
        this.logs = {
            player: [],
            ai: []
        };

        // Keyboard navigation
        this.focus = {
            board: 'player',
            row: 0,
            col: 0
        };

         // AI state
         this.ai = {
             mode: 'hunt',
             targetQueue: [],
             hits: [],
             fired: new Set(),
             queued: new Set()
         };

         // Sounds (optional; uses WebAudio)
        this.audio = {
            enabled: true,
            ctx: null,
            ambientEnabled: true,
            ambientNode: null,
            ambientGain: null
        };

         this.resetToSetup();
        this.bindUi();
        this.renderAll();
    }

     // -------------------------
     // Setup / reset
     // -------------------------
     resetToSetup() {
        this.playerBoard = this.createEmptyBoard();
        this.computerBoard = this.createEmptyBoard();

         this.playerShips = this.createShips('P');
         this.computerShips = this.createShips('C');

         this.phase = 'setup';
         this.shipOrientation = 'horizontal';
         this.selectedShipId = this.playerShips[0]?.id ?? null;

         this.ai.mode = 'hunt';
        this.ai.targetQueue = [];
        this.ai.hits = [];
        this.ai.fired = new Set();
        this.ai.queued = new Set();

        this.logs.player = [];
        this.logs.ai = [];

         this.focus = { board: 'player', row: 0, col: 0 };

         this.setTurnIndicator('Setup: Place your ships');
         this.setStatus('Place your ships to begin!');
         this.setSunkMessage('');

         this.clearGameResultStyles();
         this.stopAmbient();

         this.ensureShipSelector();
        this.updateShipSelector();
        this.renderHealthPanels();
        this.renderLogs();
        this.syncControlStateToUi();
    }

     createEmptyBoard() {
         const b = [];
         for (let r = 0; r < this.boardSize; r++) {
             b[r] = [];
             for (let c = 0; c < this.boardSize; c++) {
                 b[r][c] = {
                     shipId: null,
                     hit: false
                 };
             }
         }
         return b;
     }

     createShips(prefix) {
         return this.shipTypes.map((t, idx) => ({
             id: `${prefix}-${idx}`,
             name: t.name,
             size: t.size,
             placed: false,
             sunk: false,
             positions: [],
             hits: new Set()
         }));
     }

     bindUi() {
        document.getElementById('start-restart')?.addEventListener('click', () => {
            if (this.phase === 'setup') {
                const allPlaced = this.playerShips.every((s) => s.placed);
                if (allPlaced) {
                    this.startBattleIfReady();
                    return;
                }
            }

            this.resetToSetup();
            this.renderAll();
        });
        document.getElementById('auto-place')?.addEventListener('click', () => this.autoPlacePlayerShips());

        document.getElementById('rotate-ship')?.addEventListener('click', () => {
            if (this.phase !== 'setup') return;
            this.toggleOrientation();
        });

        document.getElementById('difficulty')?.addEventListener('change', (e) => {
            this.difficulty = e.target.value;
        });

        document.getElementById('ambient')?.addEventListener('change', (e) => {
            this.audio.ambientEnabled = Boolean(e.target.checked);
            this.updateAmbient();
        });

        document.getElementById('mute')?.addEventListener('click', () => {
            this.audio.enabled = !this.audio.enabled;
            this.updateAudioUi();
            this.updateAmbient();
        });

        // Global keyboard
        document.addEventListener('keydown', (e) => this.handleGlobalKeydown(e));
    }

     // -------------------------
     // Rendering
     // -------------------------
     renderAll() {
        this.renderBoard('player');
        this.renderBoard('computer');
        this.updateStats();
        this.updateInteractivity();
        this.renderHealthPanels();
        this.renderLogs();
        this.syncFocusToDom();
    }

    ensureShipSelector() {
        if (document.getElementById('ship-selector')) return;

        const playerBoardEl = document.getElementById('player-board');
        if (!playerBoardEl) return;

        const healthEl = document.getElementById('player-health');
        const healthSection = healthEl?.closest('div.mt-5');
        const container = document.createElement('div');
        container.className = 'mt-5';

        const title = document.createElement('h3');
        title.className = 'text-sm font-bold text-blue-100 mb-2';
        title.textContent = 'Shipyard';

        const selector = document.createElement('div');
        selector.id = 'ship-selector';
        selector.className = 'flex flex-wrap justify-center gap-3';

        container.appendChild(title);
        container.appendChild(selector);

        const parent = playerBoardEl.parentElement;
        if (!parent) return;

        if (healthSection && healthSection.parentElement === parent) {
            parent.insertBefore(container, healthSection);
        } else {
            parent.appendChild(container);
        }
    }

     renderBoard(which) {
         const boardId = which === 'player' ? 'player-board' : 'computer-board';
         const boardEl = document.getElementById(boardId);
         const board = which === 'player' ? this.playerBoard : this.computerBoard;

         boardEl.innerHTML = '';

         for (let r = 0; r < this.boardSize; r++) {
             for (let c = 0; c < this.boardSize; c++) {
                 const cellEl = document.createElement('div');
                 cellEl.className = 'cell';
                 cellEl.dataset.board = which;
                 cellEl.dataset.row = String(r);
                 cellEl.dataset.col = String(c);
                 cellEl.setAttribute('role', 'gridcell');
                 cellEl.setAttribute('aria-label', `${which === 'player' ? 'Your' : 'Enemy'} cell ${r + 1}, ${c + 1}`);
                 cellEl.tabIndex = -1;

                 // Base water color
                 cellEl.classList.add(which === 'player' ? 'player-water' : 'ai-water');

                 const cell = board[r][c];
                 const ship = cell.shipId ? this.getShip(which, cell.shipId) : null;
                 const isHit = cell.hit;

                 if (which === 'player') {
                    if (cell.shipId && ship && !ship.sunk) {
                        cellEl.classList.add('player-ship', 'ship-seg');

                        const posSet = new Set(ship.positions.map(([rr, cc]) => `${rr},${cc}`));
                        const hasLeft = posSet.has(`${r},${c - 1}`);
                        const hasRight = posSet.has(`${r},${c + 1}`);
                        const hasUp = posSet.has(`${r - 1},${c}`);
                        const hasDown = posSet.has(`${r + 1},${c}`);

                        const isHorizontal = hasLeft || hasRight;
                        const isVertical = hasUp || hasDown;

                        if (!isHorizontal && !isVertical) {
                            cellEl.classList.add('ship-single');
                        } else if (isHorizontal) {
                            cellEl.classList.add('ship-h');
                            if (!hasLeft && hasRight) cellEl.classList.add('ship-head');
                            else if (hasLeft && !hasRight) cellEl.classList.add('ship-tail');
                            else cellEl.classList.add('ship-mid');
                        } else {
                            cellEl.classList.add('ship-v');
                            if (!hasUp && hasDown) cellEl.classList.add('ship-head');
                            else if (hasUp && !hasDown) cellEl.classList.add('ship-tail');
                            else cellEl.classList.add('ship-mid');
                        }
                    }
                     if (isHit) {
                         if (cell.shipId) {
                             cellEl.classList.add(ship && ship.sunk ? 'sunk' : 'ai-hit');
                         } else {
                             cellEl.classList.add('miss');
                         }
                     }

                     if (this.phase === 'setup') {
                         cellEl.addEventListener('click', () => this.tryPlaceSelectedShip(r, c));
                         cellEl.addEventListener('mouseenter', () => this.previewPlacement(r, c));
                         cellEl.addEventListener('mouseleave', () => this.clearPreview());

                        // Drag-and-drop placement
                        cellEl.addEventListener('dragover', (ev) => {
                            ev.preventDefault();
                            this.previewPlacement(r, c);
                        });
                        cellEl.addEventListener('dragleave', () => this.clearPreview());
                        cellEl.addEventListener('drop', (ev) => {
                            ev.preventDefault();
                            const shipId = ev.dataTransfer?.getData('text/plain');
                            if (!shipId) return;
                            this.selectedShipId = shipId;
                            this.tryPlaceSelectedShip(r, c);
                        });
                    }
                } else {
                     // Do not reveal enemy ships unless hit/sunk.
                     if (isHit) {
                         if (cell.shipId) {
                             cellEl.classList.add(ship && ship.sunk ? 'sunk' : 'player-hit');

                             if (ship) {
                                 cellEl.classList.add('enemy-ship', 'ship-seg');

                                 const posSet = new Set(ship.positions.map(([rr, cc]) => `${rr},${cc}`));
                                 const hasLeft = posSet.has(`${r},${c - 1}`);
                                 const hasRight = posSet.has(`${r},${c + 1}`);
                                 const hasUp = posSet.has(`${r - 1},${c}`);
                                 const hasDown = posSet.has(`${r + 1},${c}`);

                                 const isHorizontal = hasLeft || hasRight;
                                 const isVertical = hasUp || hasDown;

                                 if (!isHorizontal && !isVertical) {
                                     cellEl.classList.add('ship-single');
                                 } else if (isHorizontal) {
                                     cellEl.classList.add('ship-h');
                                     if (!hasLeft && hasRight) cellEl.classList.add('ship-head');
                                     else if (hasLeft && !hasRight) cellEl.classList.add('ship-tail');
                                     else cellEl.classList.add('ship-mid');
                                 } else {
                                     cellEl.classList.add('ship-v');
                                     if (!hasUp && hasDown) cellEl.classList.add('ship-head');
                                     else if (hasUp && !hasDown) cellEl.classList.add('ship-tail');
                                     else cellEl.classList.add('ship-mid');
                                 }
                             }
                         } else {
                             cellEl.classList.add('miss');
                         }
                     }

                     cellEl.addEventListener('click', () => this.playerFire(r, c));
                }

                 // Keyboard focus
                 cellEl.addEventListener('focus', () => {
                     this.focus.board = which;
                     this.focus.row = r;
                     this.focus.col = c;
                 });

                 boardEl.appendChild(cellEl);
            }
        }
    }

     updateInteractivity() {
         const isPlayerTurn = this.phase === 'player_turn';
         const isAiTurn = this.phase === 'ai_turn';
         const isSetup = this.phase === 'setup';

         const computerCells = document.querySelectorAll('#computer-board .cell');
         computerCells.forEach((cell) => {
             const r = Number(cell.dataset.row);
             const c = Number(cell.dataset.col);
             const alreadyShot = this.computerBoard[r][c].hit;
             const clickable = isPlayerTurn && !alreadyShot;
             cell.classList.toggle('ai-clickable', clickable);
             cell.classList.toggle('disabled', !clickable);
             cell.setAttribute('aria-disabled', String(!clickable));
         });

         // During setup, focus stays on player board; during battle, default focus to computer board.
         if (isSetup) {
             this.focus.board = 'player';
         } else if (isPlayerTurn && this.focus.board !== 'computer') {
             this.focus.board = 'computer';
         } else if (isAiTurn) {
             // keep focus but disallow actions
         }
    }

     updateShipSelector() {
         const container = document.getElementById('ship-selector');
         if (!container) return;

         if (this.phase !== 'setup') {
             container.style.display = 'none';
             return;
         }

         container.style.display = '';
         container.innerHTML = '';

         this.playerShips.forEach((ship) => {
            const piece = document.createElement('button');
            piece.type = 'button';
            piece.className = 'ship-piece';
            piece.style.width = `${ship.size * 42}px`;
            piece.style.height = '40px';
            piece.dataset.shipId = ship.id;
            piece.setAttribute('aria-label', `${ship.name}, size ${ship.size}${ship.placed ? ', placed' : ''}`);
            piece.disabled = ship.placed;

            piece.draggable = !ship.placed;
            piece.addEventListener('dragstart', (ev) => {
                if (ship.placed) return;
                ev.dataTransfer?.setData('text/plain', ship.id);
            });

             if (ship.placed) {
                 piece.style.opacity = '0.4';
                 piece.style.cursor = 'not-allowed';
             }

             if (ship.id === this.selectedShipId) {
                 piece.classList.add('selected');
             }

             piece.addEventListener('click', () => {
                this.selectedShipId = ship.id;
                this.renderAll();
            });

             container.appendChild(piece);
         });
    }

    // -------------------------
    // Health + logs
    // -------------------------
    renderHealthPanels() {
        this.renderHealthPanel('player');
        this.renderHealthPanel('computer');
    }

    renderHealthPanel(which) {
        const containerId = which === 'player' ? 'player-health' : 'computer-health';
        const container = document.getElementById(containerId);
        if (!container) return;

        const ships = which === 'player' ? this.playerShips : this.computerShips;
        const board = which === 'player' ? this.playerBoard : this.computerBoard;

        container.innerHTML = '';

        ships.forEach((ship) => {
            const total = ship.size;
            const remaining = ship.positions.length === 0
                ? total
                : ship.positions.filter(([r, c]) => !board[r][c].hit).length;

            const row = document.createElement('div');
            row.className = 'health-row';

            const label = document.createElement('div');
            label.className = 'health-label';
            label.textContent = ship.name;

            const bar = document.createElement('div');
            bar.className = 'health-bar';
            const fill = document.createElement('div');
            fill.className = `health-fill ${which}`;
            fill.style.width = `${Math.max(0, Math.min(100, (remaining / total) * 100))}%`;
            bar.appendChild(fill);

            const text = document.createElement('div');
            text.className = 'health-text';
            text.textContent = `${remaining}/${total}`;

            row.appendChild(label);
            row.appendChild(bar);
            row.appendChild(text);
            container.appendChild(row);
        });
    }

    addMoveLog(which, text, outcome) {
        const arr = which === 'player' ? this.logs.player : this.logs.ai;
        arr.unshift({ text, outcome });
        if (arr.length > 5) arr.length = 5;
    }

    renderLogs() {
        const p = document.getElementById('player-log');
        const a = document.getElementById('ai-log');
        if (p) this.renderLogList(p, this.logs.player);
        if (a) this.renderLogList(a, this.logs.ai);
    }

    renderLogList(container, items) {
        container.innerHTML = '';
        items.forEach((it) => {
            const li = document.createElement('li');
            li.className = 'move-item';
            const msg = document.createElement('span');
            msg.textContent = it.text;
            const badge = document.createElement('span');
            badge.className = `move-badge ${it.outcome}`;
            badge.textContent = it.outcome.toUpperCase();
            li.appendChild(msg);
            li.appendChild(badge);
            container.appendChild(li);
        });
    }

     getShip(which, shipId) {
         const list = which === 'player' ? this.playerShips : this.computerShips;
         return list.find((s) => s.id === shipId) ?? null;
     }

     getPositions(row, col, size, orientation) {
         const positions = [];
         for (let i = 0; i < size; i++) {
             const r = orientation === 'horizontal' ? row : row + i;
             const c = orientation === 'horizontal' ? col + i : col;
             positions.push([r, c]);
         }
         return positions;
     }

     canPlaceOn(board, positions) {
         for (const [r, c] of positions) {
             if (r < 0 || r >= this.boardSize || c < 0 || c >= this.boardSize) return false;
             if (board[r][c].shipId) return false;
         }
         return true;
     }

     previewPlacement(row, col) {
         if (this.phase !== 'setup') return;
         const ship = this.getShip('player', this.selectedShipId);
         if (!ship || ship.placed) return;

         this.clearPreview();
         const positions = this.getPositions(row, col, ship.size, this.shipOrientation);
         const ok = this.canPlaceOn(this.playerBoard, positions);
         for (const [r, c] of positions) {
             const el = document.querySelector(`#player-board .cell[data-row="${r}"][data-col="${c}"]`);
             if (el) el.classList.add(ok ? 'preview' : 'invalid');
         }
     }

     clearPreview() {
         document.querySelectorAll('.preview, .invalid').forEach((el) => {
             el.classList.remove('preview', 'invalid');
         });
     }

     tryPlaceSelectedShip(row, col) {
         if (this.phase !== 'setup') return;
         const ship = this.getShip('player', this.selectedShipId);
         if (!ship || ship.placed) return;

         const positions = this.getPositions(row, col, ship.size, this.shipOrientation);
         if (!this.canPlaceOn(this.playerBoard, positions)) return;

         ship.placed = true;
         ship.positions = positions;
         positions.forEach(([r, c]) => {
             this.playerBoard[r][c].shipId = ship.id;
         });

         // Pick next unplaced ship
        const next = this.playerShips.find((s) => !s.placed);
        this.selectedShipId = next ? next.id : null;
        if (!next) {
            this.setStatus('All ships placed! Click Start / Restart to begin the battle.');
        }

         this.updateShipSelector();
        this.renderAll();
    }

    toggleOrientation() {
        this.shipOrientation = this.shipOrientation === 'horizontal' ? 'vertical' : 'horizontal';
        this.setStatus(`Rotation: ${this.shipOrientation}`);
        this.renderAll();
    }

     autoPlacePlayerShips() {
         if (this.phase !== 'setup') return;

         // Reset just the player's placement
        const tryPlaceAll = () => {
            this.playerBoard = this.createEmptyBoard();
            this.playerShips.forEach((s) => {
                s.placed = false;
                s.sunk = false;
                s.positions = [];
                s.hits = new Set();
            });

            for (const ship of this.playerShips) {
                let placed = false;
                let attempts = 0;
                while (!placed && attempts < 500) {
                    const r = Math.floor(Math.random() * this.boardSize);
                    const c = Math.floor(Math.random() * this.boardSize);
                    const o = Math.random() < 0.5 ? 'horizontal' : 'vertical';
                    const positions = this.getPositions(r, c, ship.size, o);
                    if (this.canPlaceOn(this.playerBoard, positions)) {
                        ship.placed = true;
                        ship.positions = positions;
                        positions.forEach(([rr, cc]) => {
                            this.playerBoard[rr][cc].shipId = ship.id;
                        });
                        placed = true;
                    }
                    attempts++;
                }
                if (!placed) return false;
            }
            return true;
        };

        let ok = false;
        for (let i = 0; i < 6 && !ok; i++) ok = tryPlaceAll();

        if (!ok) {
            this.setStatus('Auto-place failed. Please try again.');
            this.renderAll();
            return;
        }

         this.selectedShipId = null;
         this.setStatus('Ships auto-placed! Click Start / Restart to begin the battle.');
         this.renderAll();

        // If you want the battle to start immediately after auto-place, uncomment:
        // this.startBattleIfReady();
     }

     startBattleIfReady() {
         if (this.phase !== 'setup') return;
         const allPlaced = this.playerShips.every((s) => s.placed);
         if (!allPlaced) {
             this.setStatus('Please place all ships first!');
             return;
         }

         this.placeComputerShipsRandom();
         this.phase = 'player_turn';
         this.setTurnIndicator('Your Turn');
         this.setStatus('Fire on the enemy grid.');
         this.setSunkMessage('');
         this.updateShipSelector();
         this.updateAmbient();
         this.renderAll();
     }

     placeComputerShipsRandom() {
         const tryPlaceAll = () => {
             this.computerBoard = this.createEmptyBoard();
             this.computerShips.forEach((s) => {
                 s.placed = false;
                 s.sunk = false;
                 s.positions = [];
                 s.hits = new Set();
             });

             for (const ship of this.computerShips) {
                 let placed = false;
                 let attempts = 0;
                 while (!placed && attempts < 500) {
                     const r = Math.floor(Math.random() * this.boardSize);
                     const c = Math.floor(Math.random() * this.boardSize);
                     const o = Math.random() < 0.5 ? 'horizontal' : 'vertical';
                     const positions = this.getPositions(r, c, ship.size, o);
                     if (this.canPlaceOn(this.computerBoard, positions)) {
                         ship.placed = true;
                         ship.positions = positions;
                         positions.forEach(([rr, cc]) => {
                             this.computerBoard[rr][cc].shipId = ship.id;
                         });
                         placed = true;
                     }
                     attempts++;
                 }
                 if (!placed) return false;
             }
             return true;
         };

         let ok = false;
         for (let i = 0; i < 6 && !ok; i++) ok = tryPlaceAll();

         if (!ok) {
             // Extremely unlikely; keep game playable.
             this.computerBoard = this.createEmptyBoard();
             this.computerShips.forEach((s) => {
                 s.placed = false;
                 s.sunk = false;
                 s.positions = [];
                 s.hits = new Set();
             });
         }
     }

     // -------------------------
     // Player turn
     // -------------------------
     playerFire(row, col) {
         if (this.phase === 'setup') {
             const allPlaced = this.playerShips.every((s) => s.placed);
             if (!allPlaced) {
                 this.setStatus('Please place all ships first!');
             } else {
                 this.setStatus('Click Start / Restart to begin the battle.');
             }
             return;
         }

         if (this.phase !== 'player_turn') return;
         if (this.computerBoard[row][col].hit) return;

         this.setSunkMessage('');
         const result = this.applyShot('computer', row, col);
         this.addMoveLog('player', `(${row + 1}, ${col + 1})`, result.outcome);
         this.renderAll();

         if (result.outcome === 'hit') {
             this.setStatus('Hit!');
             this.playSound('hit');
         } else {
             this.setStatus('Miss.');
             this.playSound('miss');
         }

         if (result.sunkShip) {
             this.setSunkMessage(`You sunk the AI's ${result.sunkShip.name}!`);
             this.playSound('sunk');
         }

         if (this.checkGameOver()) return;

         this.phase = 'ai_turn';
         this.setTurnIndicator('AI Turn');
         this.updateInteractivity();
         this.syncFocusToDom();
         setTimeout(() => this.aiMove(), 650);
     }

     applyShot(targetWhich, row, col) {
         const board = targetWhich === 'player' ? this.playerBoard : this.computerBoard;
         const ships = targetWhich === 'player' ? this.playerShips : this.computerShips;

         const cell = board[row][col];
         cell.hit = true;

         if (!cell.shipId) {
             return { outcome: 'miss', sunkShip: null };
         }

         const ship = ships.find((s) => s.id === cell.shipId);
         if (!ship) return { outcome: 'hit', sunkShip: null };

         ship.hits.add(`${row},${col}`);
         const sunk = ship.positions.every(([r, c]) => board[r][c].hit);
         if (sunk && !ship.sunk) {
             ship.sunk = true;
             return { outcome: 'hit', sunkShip: ship };
         }
         return { outcome: 'hit', sunkShip: null };
     }

     // -------------------------
     // Smart AI
     // -------------------------
     aiMove() {
         if (this.phase !== 'ai_turn') return;

         const [row, col] = this.aiChooseShot();
         if (row == null) return;

         this.setSunkMessage('');
         const result = this.applyShot('player', row, col);
         this.ai.fired.add(`${row},${col}`);
         this.addMoveLog('ai', `(${row + 1}, ${col + 1})`, result.outcome);

         if (result.outcome === 'hit') {
             this.setStatus('AI hit your ship!');
             this.playSound('hit');
             this.aiRegisterHit(row, col);
         } else {
             this.setStatus('AI missed.');
             this.playSound('miss');
         }

         if (result.sunkShip) {
             this.setSunkMessage(`AI sunk your ${result.sunkShip.name}!`);
             this.playSound('sunk');
             this.aiResetTargeting();
         }

         this.renderAll();
         if (this.checkGameOver()) return;

         this.phase = 'player_turn';
         this.setTurnIndicator('Your Turn');
         this.updateInteractivity();
         this.syncFocusToDom();
     }

     aiChooseShot() {
         if (this.difficulty === 'easy') {
             return this.aiChooseRandomShot();
         }

         while (this.ai.targetQueue.length > 0) {
             const [r, c] = this.ai.targetQueue.shift();
             this.ai.queued.delete(`${r},${c}`);
             if (!this.isInBounds(r, c)) continue;
             if (this.playerBoard[r][c].hit) continue;
             return [r, c];
         }

         if (this.difficulty === 'hard') {
             return this.aiChooseProbabilityShot();
         }

         return this.aiChooseParityShot();
     }

     aiChooseRandomShot() {
         const candidates = [];
         for (let r = 0; r < this.boardSize; r++) {
             for (let c = 0; c < this.boardSize; c++) {
                 if (!this.playerBoard[r][c].hit) candidates.push([r, c]);
             }
         }
         const pick = candidates[Math.floor(Math.random() * candidates.length)];
         return pick ?? [null, null];
     }

     aiChooseParityShot() {
         const candidates = [];
         for (let r = 0; r < this.boardSize; r++) {
             for (let c = 0; c < this.boardSize; c++) {
                 if (this.playerBoard[r][c].hit) continue;
                 if ((r + c) % 2 === 0) candidates.push([r, c]);
             }
         }
         if (candidates.length === 0) return this.aiChooseRandomShot();
         const pick = candidates[Math.floor(Math.random() * candidates.length)];
         return pick ?? [null, null];
     }

     aiChooseProbabilityShot() {
         const remainingSizes = this.playerShips.filter((s) => !s.sunk).map((s) => s.size);
         const heat = [];
         for (let r = 0; r < this.boardSize; r++) {
             heat[r] = [];
             for (let c = 0; c < this.boardSize; c++) heat[r][c] = 0;
         }

         const canPlaceSegment = (positions) => {
             for (const [r, c] of positions) {
                 if (!this.isInBounds(r, c)) return false;
                 if (this.playerBoard[r][c].hit && !this.playerBoard[r][c].shipId) return false;
             }
             return true;
         };

         for (const size of remainingSizes) {
             for (let r = 0; r < this.boardSize; r++) {
                 for (let c = 0; c < this.boardSize; c++) {
                     const horiz = this.getPositions(r, c, size, 'horizontal');
                     if (canPlaceSegment(horiz)) {
                         horiz.forEach(([rr, cc]) => {
                             if (!this.playerBoard[rr][cc].hit) heat[rr][cc] += 1;
                         });
                     }

                     const vert = this.getPositions(r, c, size, 'vertical');
                     if (canPlaceSegment(vert)) {
                         vert.forEach(([rr, cc]) => {
                             if (!this.playerBoard[rr][cc].hit) heat[rr][cc] += 1;
                         });
                     }
                 }
             }
         }

         let best = null;
         let bestScore = -1;
         for (let r = 0; r < this.boardSize; r++) {
             for (let c = 0; c < this.boardSize; c++) {
                 if (this.playerBoard[r][c].hit) continue;
                 const score = heat[r][c];
                 if (score > bestScore) {
                     bestScore = score;
                     best = [r, c];
                 }
             }
         }

         return best ?? this.aiChooseRandomShot();
     }

     aiRegisterHit(row, col) {
         this.ai.hits.push([row, col]);

         if (this.ai.hits.length === 1) {
             this.enqueueNeighbors(row, col);
             return;
         }

         const dir = this.inferHitDirection(this.ai.hits);
         if (!dir) {
             this.enqueueNeighbors(row, col);
             return;
         }

         const line = this.ai.hits.slice().sort((a, b) => (dir === 'horizontal' ? a[1] - b[1] : a[0] - b[0]));
         const first = line[0];
         const last = line[line.length - 1];

         const extensions = [];
         if (dir === 'horizontal') {
             extensions.push([first[0], first[1] - 1]);
             extensions.push([last[0], last[1] + 1]);
         } else {
             extensions.push([first[0] - 1, first[1]]);
             extensions.push([last[0] + 1, last[1]]);
         }

         for (let i = extensions.length - 1; i >= 0; i--) {
             const [r, c] = extensions[i];
             if (!this.isInBounds(r, c)) continue;
             if (this.playerBoard[r][c].hit) continue;
             const key = `${r},${c}`;
             if (this.ai.queued.has(key)) continue;
             this.ai.queued.add(key);
             this.ai.targetQueue.unshift([r, c]);
         }
     }

     aiResetTargeting() {
         this.ai.mode = 'hunt';
         this.ai.targetQueue = [];
         this.ai.hits = [];
         this.ai.queued = new Set();
     }

     inferHitDirection(hits) {
         if (hits.length < 2) return null;
         const [r0, c0] = hits[0];
         for (let i = 1; i < hits.length; i++) {
             const [r, c] = hits[i];
             if (r === r0 && c !== c0) return 'horizontal';
             if (c === c0 && r !== r0) return 'vertical';
         }
         return null;
     }

     isInBounds(r, c) {
         return r >= 0 && r < this.boardSize && c >= 0 && c < this.boardSize;
     }

     enqueueNeighbors(row, col) {
         const candidates = [
             [row - 1, col],
             [row + 1, col],
             [row, col - 1],
             [row, col + 1]
         ];

         for (const [r, c] of candidates) {
             if (!this.isInBounds(r, c)) continue;
             if (this.playerBoard[r][c].hit) continue;
             const key = `${r},${c}`;
             if (this.ai.queued.has(key)) continue;
             this.ai.queued.add(key);
             this.ai.targetQueue.push([r, c]);
         }
         this.ai.mode = 'target';
     }

     // -------------------------
     // Game over
     // -------------------------
     checkGameOver() {
         const playerRemaining = this.playerShips.filter((s) => !s.sunk).length;
         const computerRemaining = this.computerShips.filter((s) => !s.sunk).length;

         if (computerRemaining === 0) {
             this.phase = 'game_over';
             this.setTurnIndicator('Game Over');
             this.setStatus('🎉 Victory! You sunk the enemy fleet!');
             this.applyGameResultStyles(true);
             this.stopAmbient();
             this.renderAll();
             return true;
         }
         if (playerRemaining === 0) {
             this.phase = 'game_over';
             this.setTurnIndicator('Game Over');
             this.setStatus('💀 Defeat! Your fleet was destroyed!');
             this.applyGameResultStyles(false);
             this.stopAmbient();
             this.renderAll();
             return true;
         }
         return false;
     }

     applyGameResultStyles(playerWon) {
         const el = document.getElementById('game-status');
         if (!el) return;
         el.classList.remove('victory', 'defeat');
         el.classList.add(playerWon ? 'victory' : 'defeat');
     }

     clearGameResultStyles() {
         const el = document.getElementById('game-status');
         if (!el) return;
         el.classList.remove('victory', 'defeat');
     }

     syncControlStateToUi() {
         const diff = document.getElementById('difficulty');
         if (diff && typeof diff.value === 'string') {
             this.difficulty = diff.value;
         }

         const ambient = document.getElementById('ambient');
         if (ambient && typeof ambient.checked === 'boolean') {
             this.audio.ambientEnabled = Boolean(ambient.checked);
         }

         this.updateAudioUi();
     }

     updateAudioUi() {
         const btn = document.getElementById('mute');
         if (!btn) return;
         btn.textContent = this.audio.enabled ? '🔊 Sound' : '🔇 Muted';
         btn.setAttribute('aria-pressed', String(!this.audio.enabled));
     }

     updateAmbient() {
         if (!this.audio.enabled || !this.audio.ambientEnabled || (this.phase !== 'player_turn' && this.phase !== 'ai_turn')) {
             this.stopAmbient();
             return;
         }
         this.startAmbient();
     }

     startAmbient() {
         const ctx = this.ensureAudioContext();
         if (!ctx) return;
         if (ctx.state === 'suspended') {
             ctx.resume().catch(() => {});
         }
         if (this.audio.ambientNode) return;

         const gain = ctx.createGain();
         gain.gain.setValueAtTime(0.02, ctx.currentTime);
         gain.connect(ctx.destination);

         const o1 = ctx.createOscillator();
         const o2 = ctx.createOscillator();
         o1.type = 'sine';
         o2.type = 'sine';
         o1.frequency.setValueAtTime(55, ctx.currentTime);
         o2.frequency.setValueAtTime(110, ctx.currentTime);
         o1.connect(gain);
         o2.connect(gain);
         o1.start();
         o2.start();

         this.audio.ambientNode = { o1, o2 };
         this.audio.ambientGain = gain;
     }

     stopAmbient() {
         if (!this.audio.ambientNode) return;
         try {
             this.audio.ambientNode.o1.stop();
             this.audio.ambientNode.o2.stop();
         } catch (_) {
             // ignore
         }
         this.audio.ambientNode = null;
         this.audio.ambientGain = null;
     }

     // -------------------------
     // Stats
     // -------------------------
     updateStats() {
         const playerShipsRemaining = this.playerShips.filter((s) => !s.sunk).length;
         const computerShipsRemaining = this.computerShips.filter((s) => !s.sunk).length;

         const playerHitsRemaining = this.playerShips.reduce((total, s) => {
             if (!s.placed) return total + s.size;
             return total + s.positions.filter(([r, c]) => !this.playerBoard[r][c].hit).length;
         }, 0);

         const computerHitsRemaining = this.computerShips.reduce((total, s) => {
             if (!s.placed) return total + s.size;
             return total + s.positions.filter(([r, c]) => !this.computerBoard[r][c].hit).length;
         }, 0);

         const ps = document.getElementById('player-ships');
         const cs = document.getElementById('computer-ships');
         const ph = document.getElementById('player-hits');
         const ch = document.getElementById('computer-hits');
         if (ps) ps.textContent = String(playerShipsRemaining);
         if (cs) cs.textContent = String(computerShipsRemaining);
         if (ph) ph.textContent = String(playerHitsRemaining);
         if (ch) ch.textContent = String(computerHitsRemaining);
     }

     // -------------------------
     // Accessibility / keyboard
     // -------------------------
     handleGlobalKeydown(e) {
         if (this.phase === 'game_over') return;

         if (e.key === 'r' || e.key === 'R') {
             if (this.phase === 'setup') {
                 this.toggleOrientation();
             }
             return;
         }

         const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
         const isActivate = e.key === 'Enter' || e.key === ' ';

         if (!isArrow && !isActivate && e.key !== 'Tab') return;

         if (isArrow || isActivate) e.preventDefault();

         if (isArrow) {
             this.moveFocusByKey(e.key);
             this.syncFocusToDom();
             return;
         }

         if (isActivate) {
             if (this.focus.board === 'player') {
                 if (this.phase === 'setup') this.tryPlaceSelectedShip(this.focus.row, this.focus.col);
             } else {
                 this.playerFire(this.focus.row, this.focus.col);
             }
         }
     }

     moveFocusByKey(key) {
         const delta = {
             ArrowUp: [-1, 0],
             ArrowDown: [1, 0],
             ArrowLeft: [0, -1],
             ArrowRight: [0, 1]
         }[key];

         if (!delta) return;
         const [dr, dc] = delta;
         const nr = Math.max(0, Math.min(this.boardSize - 1, this.focus.row + dr));
         const nc = Math.max(0, Math.min(this.boardSize - 1, this.focus.col + dc));
         this.focus.row = nr;
         this.focus.col = nc;
     }

     syncFocusToDom() {
         const boardId = this.focus.board === 'player' ? 'player-board' : 'computer-board';
         const selector = `#${boardId} .cell[data-row="${this.focus.row}"][data-col="${this.focus.col}"]`;

         // Roving tabindex
         document.querySelectorAll(`#${boardId} .cell`).forEach((el) => (el.tabIndex = -1));
         const el = document.querySelector(selector);
         if (el) {
             el.tabIndex = 0;
             el.focus({ preventScroll: true });
         }
     }

     // -------------------------
     // Status / turn UI
     // -------------------------
     setStatus(msg) {
         const el = document.getElementById('game-status');
         if (el) el.textContent = msg;
     }

     setSunkMessage(msg) {
         const el = document.getElementById('sunk-message');
         if (el) el.textContent = msg;
     }

     setTurnIndicator(msg) {
         const el = document.getElementById('turn-indicator');
         if (el) el.textContent = msg;
     }

     // -------------------------
     // Sound
     // -------------------------
     ensureAudioContext() {
         if (!this.audio.enabled) return null;
         if (this.audio.ctx) return this.audio.ctx;
         const Ctx = window.AudioContext || window.webkitAudioContext;
         if (!Ctx) return null;
         this.audio.ctx = new Ctx();
         return this.audio.ctx;
     }

     playSound(type) {
         const ctx = this.ensureAudioContext();
         if (!ctx) return;
         if (ctx.state === 'suspended') {
             // Best effort: user interaction should have occurred already, but resume just in case
             ctx.resume().catch(() => {});
         }

         const now = ctx.currentTime;
         const o = ctx.createOscillator();
         const g = ctx.createGain();
         o.connect(g);
         g.connect(ctx.destination);

         const presets = {
             hit: { freq: 220, dur: 0.12 },
             miss: { freq: 440, dur: 0.08 },
             sunk: { freq: 110, dur: 0.25 }
         };
         const p = presets[type] ?? presets.miss;

         o.type = 'square';
         o.frequency.setValueAtTime(p.freq, now);
         g.gain.setValueAtTime(0.0001, now);
         g.gain.exponentialRampToValueAtTime(0.06, now + 0.01);
         g.gain.exponentialRampToValueAtTime(0.0001, now + p.dur);

         o.start(now);
         o.stop(now + p.dur);
     }
 }

 // Initialize game when page loads
 window.addEventListener('DOMContentLoaded', () => {
     window.game = new BattleshipGame();
 });
