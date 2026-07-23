"use client";

import { useState, useEffect } from "react";
import { useQueryState } from "nuqs";
import { StreamProvider } from "./StreamProvider";
import { SessionProvider } from "./SessionProvider";
import { ArtifactProvider } from "./thread/artifact";
import { Thread } from "./thread";
import { NewSessionModal } from "./NewSessionModal";

export function ChatView({
  readOnly = false,
}: {
  readOnly?: boolean;
}) {
  return (
    <SessionProvider>
      <StreamProvider readOnly={readOnly}>
        <ArtifactProvider>
          <ChatContent readOnly={readOnly} />
        </ArtifactProvider>
      </StreamProvider>
    </SessionProvider>
  );
}

function ChatContent({ readOnly }: { readOnly: boolean }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [projectPreselect, setProjectPreselect] = useState<
    string | undefined
  >(undefined);
  const [sessionId, setSessionId] = useQueryState("session");
  const [projectParam, setProjectParam] = useQueryState("project");

  useEffect(() => {
    if (projectParam) {
      setProjectPreselect(projectParam);
      setModalOpen(true);
      setProjectParam(null);
    }
  }, [projectParam, setProjectParam]);

  return (
    <div className="h-full">
      <Thread
        onNewSession={
          readOnly ? undefined : () => {
            setProjectPreselect(undefined);
            setModalOpen(true);
          }
        }
      />
      <NewSessionModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setProjectPreselect(undefined);
        }}
        onCreated={(id) => setSessionId(id)}
        preselectProjectId={projectPreselect}
      />
    </div>
  );
}
