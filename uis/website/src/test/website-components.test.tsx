import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopNav } from "@/components/website/TopNav";
import { SectionTitle } from "@/components/website/SectionTitle";
import { Footer } from "@/components/website/Footer";

describe("Website Components", () => {
  describe("TopNav", () => {
    it("renders brand link, navigation links and careers CTA", () => {
      render(<TopNav />);

      expect(screen.getByRole("link", { name: "Brasaland inicio" })).toHaveAttribute("href", "#inicio");
      expect(screen.getByRole("link", { name: "Experiencia" })).toHaveAttribute("href", "#menu");
      expect(screen.getByRole("link", { name: "Locales" })).toHaveAttribute("href", "#locales");
      expect(screen.getByRole("link", { name: "Nosotros" })).toHaveAttribute("href", "#nosotros");
      expect(screen.getByRole("link", { name: "Rewards" })).toHaveAttribute("href", "#rewards");
      expect(screen.getByRole("link", { name: "Unete al Equipo" })).toHaveAttribute("href", "/careers");
    });
  });

  describe("SectionTitle", () => {
    it("renders title, optional eyebrow and subtitle", () => {
      render(
        <SectionTitle
          eyebrow="Sabor Auténtico"
          title="Nuestra Carta"
          subtitle="Platos a la brasa con tradición colombiana"
        />
      );

      expect(screen.getByText("Sabor Auténtico")).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 2, name: "Nuestra Carta" })).toBeInTheDocument();
      expect(screen.getByText("Platos a la brasa con tradición colombiana")).toBeInTheDocument();
    });

    it("renders correctly without eyebrow and subtitle", () => {
      render(<SectionTitle title="Locales" />);

      expect(screen.getByRole("heading", { level: 2, name: "Locales" })).toBeInTheDocument();
    });
  });

  describe("Footer", () => {
    it("renders copyright, social links and legal links", () => {
      render(<Footer />);

      expect(screen.getByText(/© 2026 BRASALAND EST. 2008/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Instagram" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "TikTok" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Privacy" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Terms" })).toBeInTheDocument();
    });
  });
});

