import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AgentMessage } from "../../hooks/agentHooks";
import { MessageThread } from "./MessageThread";

const USER_MSG: AgentMessage = { kind: "user", text: "Book tennis tomorrow", timestamp: 1000 };
const AGENT_MSG: AgentMessage = { kind: "agent", text: "Here are available slots", timestamp: 2000 };

const noop = vi.fn();

describe("MessageThread", () => {
  it("renders user messages with user data-kind marker", () => {
    render(<MessageThread
      messages={[USER_MSG]}
      isAgentTyping={false}
      onConfirm={noop}
      onDismiss={noop}
      isConfirming={false}
    />);
    const bubble = screen.getByText("Book tennis tomorrow").closest("[data-kind]");
    expect(bubble).toHaveAttribute("data-kind", "user");
  });

  it("renders agent messages with agent data-kind marker", () => {
    render(<MessageThread
      messages={[AGENT_MSG]}
      isAgentTyping={false}
      onConfirm={noop}
      onDismiss={noop}
      isConfirming={false}
    />);
    const bubble = screen.getByText("Here are available slots").closest("[data-kind]");
    expect(bubble).toHaveAttribute("data-kind", "agent");
  });

  it("renders TypingIndicator when isAgentTyping is true", () => {
    render(<MessageThread
      messages={[]}
      isAgentTyping={true}
      onConfirm={noop}
      onDismiss={noop}
      isConfirming={false}
    />);
    expect(screen.getByTestId("typing-indicator")).toBeInTheDocument();
  });

  it("does not render TypingIndicator when isAgentTyping is false", () => {
    render(<MessageThread
      messages={[]}
      isAgentTyping={false}
      onConfirm={noop}
      onDismiss={noop}
      isConfirming={false}
    />);
    expect(screen.queryByTestId("typing-indicator")).toBeNull();
  });

  it("renders all messages in order", () => {
    render(<MessageThread
      messages={[USER_MSG, AGENT_MSG]}
      isAgentTyping={false}
      onConfirm={noop}
      onDismiss={noop}
      isConfirming={false}
    />);
    expect(screen.getByText("Book tennis tomorrow")).toBeInTheDocument();
    expect(screen.getByText("Here are available slots")).toBeInTheDocument();
  });
});
