import { useCallback } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import { MyDesignsScreen } from '@/shell/components/MyDesignsScreen'
import { OpenDesignDialog } from '@/shell/components/OpenDesignDialog'
import type { NavDestination } from '@/shell/components/GlobalNavigation'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import '@/shell/shellTokens.css'
import styles from './StudioPage.module.css'

export const STUDIO_PATH = '/studio'
export const MY_DESIGNS_PATH = '/studio/designs'

/**
 * Studio and My Designs share one mounted editor so the working draft's autosave chain,
 * IndexedDB recovery and conflict state survive switching between the two screens.
 */
export function StudioPage() {
  const editor = useStudioEditor()
  const location = useLocation()
  const navigate = useNavigate()
  const path = location.pathname.replace(/\/+$/, '') || STUDIO_PATH
  const view = path === MY_DESIGNS_PATH ? 'library' : path === STUDIO_PATH ? 'studio' : null

  const onNavigate = useCallback(
    (destination: NavDestination) => {
      navigate(destination === 'designs' ? MY_DESIGNS_PATH : STUDIO_PATH)
    },
    [navigate],
  )
  const backToStudio = useCallback(() => navigate(STUDIO_PATH), [navigate])

  if (view === null) return <Navigate to={STUDIO_PATH} replace />

  return (
    <div className={`${styles.page} studioShellRoot studio-chrome`}>
      <FashionRiseAppShell
        username={editor.user?.username ?? 'Creator'}
        onLogout={editor.onLogout}
        onComingSoon={editor.showComingSoon}
        currentNav={view === 'library' ? 'designs' : 'create'}
        onNavigate={onNavigate}
      >
        {view === 'library' && editor.user?.id ? (
          <MyDesignsScreen
            ownerId={editor.user.id}
            working={{
              strokes: editor.strokes,
              model: editor.model,
              dimmed: editor.dimmed,
              brush: {
                sizeId: editor.sizeId,
                sizePx: editor.brushSize,
                opacity: editor.opacity,
                color: editor.color,
              },
              saveStatus: editor.saveStatus,
              saveStatusLabel: editor.saveStatusLabel,
            }}
            libraryVersion={editor.libraryVersion}
            onOpen={(id) => void editor.requestOpenDesign(id)}
            onBackToStudio={backToStudio}
            opening={editor.openDesign !== null}
          />
        ) : (
          <CreatorWorkspace editor={editor} onOpenLibrary={() => onNavigate('designs')} />
        )}
      </FashionRiseAppShell>
      {editor.openDesign ? (
        <OpenDesignDialog
          state={editor.openDesign}
          onConfirm={editor.confirmOpenDesign}
          onRetry={() => void editor.retryOpenDesign()}
          onCancel={editor.cancelOpenDesign}
          onGoToStudio={() => {
            editor.cancelOpenDesign()
            backToStudio()
          }}
        />
      ) : null}
    </div>
  )
}
