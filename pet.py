"""Logica pura do Pomodoro-Tamagotchi: ciclo foco/pausa e energia/humor.

Este modulo nao importa pygame de proposito, para poder ser testado sem abrir
janela. A renderizacao fica em pomodoro.py.

Fluxo:
    FOCO (rodando) --acaba--> FOCO (aguardando o usuario marcar a pausa)
        --advance()--> PAUSA (rodando, comemorando) --acaba-->
    PAUSA (aguardando) --advance()--> FOCO ...
"""

FOCUS = "focus"
BREAK = "break"

PHASE_LABELS = {FOCUS: "FOCO", BREAK: "PAUSA"}

# Limiares de humor (energia 0..100)
EXHAUSTED_MAX = 20
TIRED_MAX = 45
OK_MAX = 75

# Eventos devolvidos por tick()/skip()/toggle()/advance()
FOCUS_DONE = "focus_done"
BREAK_DONE = "break_done"
BREAK_STARTED = "break_started"
FOCUS_STARTED = "focus_started"


class PomodoroPet:
    """Maquina de estados do ciclo Pomodoro + bichinho que cansa e descansa.

    A energia cai durante o foco e sobe durante a pausa. Os custos sao dados em
    pontos por fase completa, entao a dinamica independe da duracao escolhida.

    A troca de fase e manual: quando o tempo acaba o bichinho fica *aguardando*
    (awaiting) ate o usuario chamar advance() — o que da o gancho para a
    animacao de alegria ao comecar a pausa.
    """

    def __init__(self, focus_duration=25 * 60, break_duration=5 * 60,
                 start_energy=85.0, focus_cost=45.0, break_restore=45.0):
        self.focus_duration = float(focus_duration)
        self.break_duration = float(break_duration)
        self.start_energy = float(start_energy)
        self.focus_cost = float(focus_cost)
        self.break_restore = float(break_restore)

        self.phase = FOCUS
        self.remaining = self.focus_duration
        self.running = False
        self.awaiting = False
        self.cycles = 0
        self.energy = self.start_energy

    # --- controles ---
    def start(self):
        if not self.awaiting:
            self.running = True

    def pause(self):
        self.running = False

    def toggle(self):
        """Iniciar/pausar; se estiver aguardando, inicia a proxima fase.

        Retorna o evento da transicao (ou None).
        """
        if self.awaiting:
            return self.advance()
        self.running = not self.running
        return None

    def advance(self):
        """Comeca a proxima fase a partir do estado 'aguardando'."""
        if not self.awaiting:
            return None
        self.awaiting = False
        self.running = True
        if self.phase == FOCUS:
            self.phase = BREAK
            self.remaining = self.break_duration
            return BREAK_STARTED
        self.phase = FOCUS
        self.remaining = self.focus_duration
        return FOCUS_STARTED

    def reset(self):
        """Nova sessao completa: volta para o foco com a energia inicial."""
        self.phase = FOCUS
        self.remaining = self.focus_duration
        self.running = False
        self.awaiting = False
        self.cycles = 0
        self.energy = self.start_energy

    def skip(self):
        """Encerra a fase atual agora, deixando o bichinho aguardando."""
        return self._finish_phase()

    # --- simulacao ---
    def tick(self, dt):
        """Avanca `dt` segundos. Retorna a lista de eventos ocorridos."""
        if not self.running or self.awaiting or dt <= 0:
            return []

        step = min(float(dt), self.remaining)
        self._apply_energy(step)
        if self.remaining > dt:
            self.remaining -= dt
            return []
        return [self._finish_phase()]

    def _apply_energy(self, seconds):
        if self.phase == FOCUS:
            rate = self.focus_cost / self.focus_duration if self.focus_duration else 0.0
            self.energy -= rate * seconds
        else:
            rate = self.break_restore / self.break_duration if self.break_duration else 0.0
            self.energy += rate * seconds
        self.energy = max(0.0, min(100.0, self.energy))

    def _finish_phase(self):
        self.running = False
        self.awaiting = True
        self.remaining = 0.0
        if self.phase == FOCUS:
            self.cycles += 1
            return FOCUS_DONE
        return BREAK_DONE

    # --- consultas ---
    @property
    def duration(self):
        return self.focus_duration if self.phase == FOCUS else self.break_duration

    @property
    def next_phase(self):
        return BREAK if self.phase == FOCUS else FOCUS

    @property
    def progress(self):
        """Fracao ja decorrida da fase atual (0..1)."""
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self.remaining / self.duration))

    @property
    def mood(self):
        energy = self.energy
        if energy <= EXHAUSTED_MAX:
            return "exhausted"
        if energy <= TIRED_MAX:
            return "tired"
        if self.phase == FOCUS:
            return "focus"
        if energy <= OK_MAX:
            return "ok"
        return "happy"

    @property
    def resting(self):
        return self.phase == BREAK and self.running

    @property
    def phase_label(self):
        return PHASE_LABELS[self.phase]

    @staticmethod
    def format_time(seconds):
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"
