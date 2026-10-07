export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      style={{
        display: "flex",
        height: "100%",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--color-error)",
        fontSize: "var(--font-size-inactive)",
        textAlign: "center",
        padding: "0 2rem",
      }}
    >
      {message}
    </div>
  );
}
