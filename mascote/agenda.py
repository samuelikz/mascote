import calendar
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class Lembrete:
    id: int
    texto: str
    original: datetime
    proximo: datetime
    regra: dict | None


def _dia_vale(dia, regra: dict) -> bool:
    if regra["tipo"] == "semanal":
        return dia.weekday() in (regra.get("dias") or range(7))
    if regra["tipo"] == "mensal":
        return dia.day == min(regra["dia"], calendar.monthrange(dia.year, dia.month)[1])
    return True


def proximo_disparo(base: datetime, regra: dict, depois_de: datetime) -> datetime:
    dia = depois_de.date()
    for _ in range(400):
        candidato = datetime.combine(dia, base.time())
        if candidato > depois_de and _dia_vale(dia, regra):
            return candidato
        dia += timedelta(days=1)
    raise ValueError(f"regra sem próxima ocorrência: {regra}")


class Agenda:
    def __init__(self, caminho: Path):
        self.db = sqlite3.connect(caminho)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS lembretes (id INTEGER PRIMARY KEY, texto TEXT, original TEXT, proximo TEXT, regra_json TEXT)"
        )
        self.db.commit()

    def _sql(self, sql: str, *args):
        cur = self.db.execute(sql, args)
        self.db.commit()
        return cur

    def _ler(self, sql: str, *args) -> list[Lembrete]:
        return [
            Lembrete(i, t, datetime.fromisoformat(o), datetime.fromisoformat(p), json.loads(r) if r else None)
            for i, t, o, p, r in self.db.execute(sql, args)
        ]

    def _um(self, id: int) -> Lembrete | None:
        achados = self._ler("SELECT * FROM lembretes WHERE id = ?", id)
        return achados[0] if achados else None

    def adicionar(self, texto: str, quando: datetime, regra: dict | None = None) -> int:
        cur = self._sql(
            "INSERT INTO lembretes (texto, original, proximo, regra_json) VALUES (?, ?, ?, ?)",
            texto, quando.isoformat(), quando.isoformat(), json.dumps(regra) if regra else None,
        )
        return cur.lastrowid

    def vencidos(self, agora: datetime) -> list[Lembrete]:
        return self._ler("SELECT * FROM lembretes WHERE proximo <= ? ORDER BY proximo", agora.isoformat())

    def listar(self) -> list[Lembrete]:
        return self._ler("SELECT * FROM lembretes ORDER BY proximo")

    def feito(self, id: int, agora: datetime) -> None:
        l = self._um(id)
        if l is None:
            return
        if l.regra is None:
            self.apagar(id)
        else:
            self._sql("UPDATE lembretes SET proximo = ? WHERE id = ?", proximo_disparo(l.original, l.regra, agora).isoformat(), id)

    def adiar(self, id: int, agora: datetime, minutos: int = 10) -> None:
        self._sql("UPDATE lembretes SET proximo = ? WHERE id = ?", (agora + timedelta(minutes=minutos)).isoformat(), id)

    def apagar(self, id: int) -> None:
        self._sql("DELETE FROM lembretes WHERE id = ?", id)

    def garantir_almoco(self, hora: str = "12:00") -> None:
        """Cria o lembrete diário ALMOCO, ou muda o horário dele se `hora` for outra."""
        agora = datetime.now()
        h, m = map(int, hora.split(":"))
        original = agora.replace(hour=h, minute=m, second=0, microsecond=0)
        proximo = proximo_disparo(original, {"tipo": "diario"}, agora)
        existente = self._ler("SELECT * FROM lembretes WHERE texto = 'ALMOCO'")
        if not existente:
            self.adicionar("ALMOCO", original, {"tipo": "diario"})
            self._sql("UPDATE lembretes SET proximo = ? WHERE texto = 'ALMOCO'", proximo.isoformat())
        elif existente[0].original.time() != original.time():
            self._sql("UPDATE lembretes SET original = ?, proximo = ? WHERE texto = 'ALMOCO'", original.isoformat(), proximo.isoformat())
