import { useCallback, useMemo } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import { MyDesignsScreen } from '@/shell/components/MyDesignsScreen'
import { MyLooksScreen } from '@/shell/components/MyLooksScreen'
import { OpenDesignDialog } from '@/shell/components/OpenDesignDialog'
import type { NavDestination } from '@/shell/components/GlobalNavigation'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import '@/shell/shellTokens.css'
import styles from './StudioPage.module.css'

export const STUDIO_PATH = '/studio'
export const MY_DESIGNS_PATH = '/studio/designs'
export const MY_LOOKS_PATH = '/studio/looks'

/**
 * Studio, My Designs and My Looks share one mounted editor so the working draft's
 * autosave chain, IndexedDB recovery and conflict state survive screen switches.
 */
export function StudioPage() {
  const editor = useStudioEditor()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const path = location.pathname.replace(/\/+$/, '') || STUDIO_PATH
  const view =
    path === MY_DESIGNS_PATH
      ? 'library'
      : path === MY_LOOKS_PATH
        ? 'looks'
        : path === STUDIO_PATH
          ? 'studio'
          : null

  const onNavigate = useCallback(
    (destination: NavDestination) => {
      if (destination === 'designs') navigate(MY_DESIGNS_PATH)
      else if (destination === 'looks') navigate(MY_LOOKS_PATH)
      else navigate(STUDIO_PATH)
    },
    [navigate],
  )
  const backToStudio = useCallback(() => navigate(STUDIO_PATH), [navigate])
  const focusLookId = searchParams.get('look')
  const clearFocusLook = useCallback(() => {
    if (!searchParams.has('look')) return
    const next = new URLSearchParams(searchParams)
    next.delete('look')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const currentNav: NavDestination = useMemo(() => {
    if (view === 'library') return 'designs'
    if (view === 'looks') return 'looks'
    return 'create'
  }, [view])

  if (view === null) return <Navigate to={STUDIO_PATH} replace />

  return (
    <div className={`${styles.page} studioShellRoot studio-chrome`}>
      <FashionRiseAppShell
        username={editor.user?.username ?? 'Creator'}
        onLogout={editor.onLogout}
        onComingSoon={editor.showComingSoon}
        currentNav={currentNav}
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
        ) : view === 'looks' ? (
          <MyLooksScreen
            focusLookId={focusLookId}
            onBackToStudio={backToStudio}
            onFocusConsumed={clearFocusLook}
          />
        ) : (
          <CreatorWorkspace
            editor={editor}
            onOpenLibrary={() => onNavigate('designs')}
            onOpenLooks={(lookId) =>
              navigate(lookId ? `${MY_LOOKS_PATH}?look=${encodeURIComponent(lookId)}` : MY_LOOKS_PATH)
            }
          />
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
