export function accountCreationBlocker(online: boolean, username: string, name: string, temporary: string, mode: 'http' | 'mock') {
  if (!online) return 'Sin conexión. Comprueba tu red antes de crear una cuenta.'
  if (!username.trim()) return 'Escribe el usuario de la nueva cuenta.'
  if (!name.trim()) return 'Escribe el nombre de la persona.'
  if (mode === 'http' && temporary.length < 12) return `La contraseña temporal necesita al menos 12 caracteres (faltan ${12 - temporary.length}).`
  return ''
}
