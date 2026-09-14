# Pomodoro Timer

Timer Pomodoro minimalista em Python com Tkinter. Janela flutuante, sem bordas, semi-transparente, com animação de alerta ao final do ciclo.

## Funcionalidades

- **25 minutos** de contagem regressiva
- Janela **sem bordas** e **sempre no topo**
- **Semi-transparente** (70%), fica opaca ao passar o mouse
- Efeito de **hover**: muda cor para verde ao passar o mouse
- **Arrastável**: clique e arraste para mover
- **Animação de alerta**: flash vermelho + janela treme ao chegar em 00:00
- **Menu de contexto**: clique direito para acessar opções

## Como executar

```bash
python pomodoro.py
```

### Modo demo (timer de 5 segundos)

```bash
python pomodoro.py --demo
```

## Controles

| Ação | Botão |
|------|-------|
| Iniciar / Pausar | Clique esquerdo |
| Menu de contexto | Clique direito |
| Mover janela | Arrastar com botão esquerdo |

### Menu de contexto (clique direito)

| Opção | Ação |
|-------|------|
| Iniciar / Pausar | Alterna entre iniciar e pausar o timer |
| Reset | Reinicia o timer para 25:00 |
| Sair | Fecha a aplicação |

## Requisitos

- Python 3.x
- Tkinter (incluído na instalação padrão do Python)

## Testes

```bash
pip install pytest
pytest tests/ -v
```
