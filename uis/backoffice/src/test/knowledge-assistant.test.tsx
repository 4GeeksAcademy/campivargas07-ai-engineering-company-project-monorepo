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

  it("shows loading, blocks duplicate submissions and renders the pending answer", async () => {
    let resolveAnswer!: (value: { answer: string }) => void;
    vi.mocked(askKnowledge).mockReturnValue(new Promise((resolve) => { resolveAnswer = resolve; }));
    render(<KnowledgeAssistant />);
    fireEvent.change(screen.getByLabelText("¿Qué necesitas saber?"), { target: { value: "¿Qué aplica?" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(screen.getByRole("status")).toHaveTextContent("Buscando en los manuales");
    expect(screen.getByRole("button", { name: "Consultando…" })).toBeDisabled();
    expect(screen.getByLabelText("¿Qué necesitas saber?")).toBeDisabled();
    fireEvent.submit(screen.getByLabelText("¿Qué necesitas saber?").closest("form")!);
    expect(askKnowledge).toHaveBeenCalledOnce();
    resolveAnswer({ answer: "Respuesta del manual." });
    expect(await screen.findByLabelText("Respuesta del asistente")).toHaveTextContent("Respuesta del manual.");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("retries the preserved question after an error and clears the error on success", async () => {
    vi.mocked(askKnowledge)
      .mockRejectedValueOnce(new Error("Servicio no disponible."))
      .mockResolvedValueOnce({ answer: "Respuesta recuperada." });
    render(<KnowledgeAssistant />);
    fireEvent.change(screen.getByLabelText("¿Qué necesitas saber?"), { target: { value: "¿Qué aplica?" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Servicio no disponible.");
    expect(screen.getByLabelText("¿Qué necesitas saber?")).toHaveValue("¿Qué aplica?");
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByLabelText("Respuesta del asistente")).toHaveTextContent("Respuesta recuperada.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(askKnowledge).toHaveBeenNthCalledWith(2, "¿Qué aplica?");
  });
});
