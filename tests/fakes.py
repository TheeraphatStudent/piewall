from piewall.model import Rule


class FakeBackend:
    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules = list(rules or [])

    def list_rules(self) -> list[Rule]:
        return list(self.rules)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def delete_rules(self, name: str) -> int:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.name != name]
        return before - len(self.rules)

    def _replace(self, name: str, **changes) -> int:
        from dataclasses import replace

        n = 0
        for i, r in enumerate(self.rules):
            if r.name == name:
                self.rules[i] = replace(r, **changes)
                n += 1
        return n

    def set_enabled(self, name: str, enabled: bool) -> int:
        return self._replace(name, enabled=enabled)

    def set_action(self, name: str, action: str) -> int:
        return self._replace(name, action=action)
