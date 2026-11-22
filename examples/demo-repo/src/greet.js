export function greet(name) {
  if (!name || name.trim() === "") {
    throw new Error("nombre requerido");
  }
  return `Hola, ${name}!`;
}
