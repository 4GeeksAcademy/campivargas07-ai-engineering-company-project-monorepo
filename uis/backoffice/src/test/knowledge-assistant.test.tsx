import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KnowledgeAssistant } from "@/components/knowledge/KnowledgeAssistant";
import { askKnowledge } from "@/lib/knowledge-api";

vi.mock("@/lib/knowledge-api", () => ({ askKnowledge: vi.fn() }));

describe("KnowledgeAssistant", () => {
  beforeEach(() => vi.clearAllMocks());

  it("submits a question and renders the answer", async () => {
    vi.mocked(askKnowledge).mockResolvedValue({ answer: "Los puntos vencen según el manual." });
    render(<KnowledgeAssistant />);
    fireEvent.change(screen.getByLabelText("¿Qué necesitas saber?"), { target: { value: " ¿Cuándo vencen? " } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    await waitFor(() => expect(screen.getByLabelText("Respuesta del asistente")).toHaveTextContent("Los puntos vencen"));
    expect(askKnowledge).toHaveBeenCalledWith("¿Cuándo vencen?");
  });

  it("shows errors accessibly", async () => {
    vi.mocked(askKnowledge).mockRejectedValue(new Error("Servicio no disponible."));
    render(<KnowledgeAssistant />);
    fireEvent.change(screen.getByLabelText("¿Qué necesitas saber?"), { target: { value: "¿Qué aplica?" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Servicio no disponible.");
  });
});
