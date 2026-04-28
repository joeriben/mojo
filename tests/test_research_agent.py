import unittest

from journal_bot import research_agent


class ResearchAgentRoutingTests(unittest.TestCase):
    def test_bezug_auf_is_not_missing_reference_intent(self):
        message = "Nun haben Whitehead und Dewey konträre Ontologien, insbesondere in Bezug auf Sprache."

        self.assertEqual(research_agent._detect_search_intent(message), "general")

    def test_method_suggestion_uses_llm_synthesis_by_default(self):
        context = (
            "## Argumenteinheiten\n"
            "- Zusammenhänge zwischen Barad, Whitehead und Dewey/Bently prüfen."
        )
        message = "Welche methodischen Zugänge nutzen ähnliche Arbeiten?"

        self.assertFalse(research_agent._should_force_argument_report(message, context))
        self.assertTrue(research_agent._should_use_focused_db_agent(message, context))

    def test_article_listing_uses_focused_db_agent(self):
        context = (
            "## Argumenteinheiten\n"
            "- Zusammenhänge zwischen Barad, Whitehead und Dewey/Bently prüfen."
        )
        message = "Welche Artikel in der MOJO-DB sind relevant für diesen Entwurf?"

        self.assertFalse(research_agent._should_force_argument_report(message, context))
        self.assertTrue(research_agent._should_use_focused_db_agent(message, context))

    def test_article_button_uses_focused_db_agent(self):
        context = (
            "## Argumenteinheiten\n"
            "- Zusammenhänge zwischen Barad, Whitehead und Dewey/Bently prüfen."
        )
        message = "Relevante Artikel in der MOJO-DB recherchieren"

        self.assertFalse(research_agent._should_force_argument_report(message, context))
        self.assertTrue(research_agent._should_use_focused_db_agent(message, context))

    def test_reference_and_counter_buttons_use_focused_db_agent(self):
        context = (
            "## Argumenteinheiten\n"
            "- Zusammenhänge zwischen Barad, Whitehead und Dewey/Bently prüfen."
        )

        for message in [
            "Fehlende Referenzen im Text prüfen",
            "Gegenargumente oder Widersprüche prüfen",
        ]:
            self.assertFalse(research_agent._should_force_argument_report(message, context))
            self.assertTrue(research_agent._should_use_focused_db_agent(message, context))

    def test_explicit_local_scan_still_short_circuits(self):
        context = (
            "## Argumenteinheiten\n"
            "- Zusammenhänge zwischen Barad, Whitehead und Dewey/Bently prüfen."
        )
        message = "Zeige eine kostenfreie Trefferliste zu methodischen Zugängen."

        self.assertTrue(research_agent._should_force_argument_report(message, context))
        self.assertFalse(research_agent._should_use_focused_db_agent(message, context))

    def test_focused_prompt_excludes_corpus_blocks(self):
        prompt = research_agent.build_focused_db_system_prompt("Kontext")

        self.assertIn("MOJO-Artikel-Datenbank", prompt)
        self.assertNotIn("EIGENE PUBLIKATIONEN", prompt)
        self.assertNotIn("KURZPROFILE DER EIGENEN PUBLIKATIONEN", prompt)

    def test_focused_search_tool_finds_dewey_bentley_candidate(self):
        result = research_agent._execute_focused_db_tool(
            "search_articles",
            {"query": "Dewey Bentley transactionalism", "limit": 5},
        )

        self.assertIn("Refurbishing learning via complexity theory", result)

    def test_focused_search_hints_include_both_comparison_sides(self):
        context = (
            "Barad wird oft mit Whitehead verbunden. Wir prüfen dagegen Barad "
            "und Dewey/Bently, insbesondere Sprache und Ontologie."
        )
        hints = research_agent._build_focused_search_hints(
            "Welche Artikel in der MOJO-DB sind relevant?",
            context,
        )

        self.assertIn("Barad Whitehead", hints)
        self.assertIn("Dewey Bentley transactionalism", hints)
        self.assertIn("Dewey pragmatism language ontology", hints)

    def test_dewey_bently_terms_are_expanded(self):
        terms = research_agent._extract_search_terms("Dewey/Bently und Knowing and the Known")

        self.assertIn("dewey", terms)
        self.assertIn("bentley", terms)


if __name__ == "__main__":
    unittest.main()
