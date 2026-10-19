import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import '@/shell/shellTokens.css'
import styles from './StudioPage.module.css'

export function StudioPage() {
  const editor = useStudioEditor()

  return (
    <div className={`${styles.page} studioShellRoot studio-chrome`}>
      <FashionRiseAppShell
        username={editor.user?.username ?? 'Creator'}
        onLogout={editor.onLogout}
        onComingSoon={editor.showComingSoon}
      >
        <CreatorWorkspace editor={editor} />
      </FashionRiseAppShell>
    </div>
  )
}
