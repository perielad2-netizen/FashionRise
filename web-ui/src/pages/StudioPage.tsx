import { useCallback, useMemo } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import { FashionStarsScreen } from '@/shell/components/FashionStarsScreen'
import { HomeScreen } from '@/shell/components/HomeScreen'
import { MyCroquisScreen } from '@/shell/components/MyCroquisScreen'
import { MyDesignsScreen } from '@/shell/components/MyDesignsScreen'
import { MyLooksScreen } from '@/shell/components/MyLooksScreen'
import { TechpackScreen } from '@/shell/components/TechpackScreen'
import { OpenDesignDialog } from '@/shell/components/OpenDesignDialog'
import type { NavDestination } from '@/shell/components/GlobalNavigation'
import { useStudioEditor } from '@/hooks/useStudioEditor'
import '@/shell/shellTokens.css'
import styles from './StudioPage.module.css'

export const STUDIO_PATH = '/studio'
export const HOME_PATH = '/studio/home'
export const MY_DESIGNS_PATH = '/studio/designs'
export const MY_LOOKS_PATH = '/studio/looks'
export const MY_CROQUIS_PATH = '/studio/croquis'
export const FASHION_STARS_PATH = '/studio/fashion-stars'
export const TECHPACK_PATH_PREFIX = '/studio/techpacks'

/**
 * Studio, My Designs, My Looks and My Croquis share one mounted editor so the
 * working draft's autosave chain, IndexedDB recovery and conflict state survive
 * screen switches.
 */
export function StudioPage() {
  const editor = useStudioEditor()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const path = location.pathname.replace(/\/+$/, '') || STUDIO_PATH
  const techpackDraftId = path.startsWith(`${TECHPACK_PATH_PREFIX}/`)
    ? path.slice(`${TECHPACK_PATH_PREFIX}/`.length).split('/').filter(Boolean)[0] || null
    : null
  const croquisEnabled = isMyCroquisUiEnabled()
  const view =
    techpackDraftId
      ? 'techpack'
      : path === MY_DESIGNS_PATH
        ? 'library'
        : path === MY_LOOKS_PATH
          ? 'looks'
          : path === MY_CROQUIS_PATH
            ? croquisEnabled
              ? 'croquis'
              : null
            : path === HOME_PATH
              ? 'home'
              : path === FASHION_STARS_PATH
                ? 'fashion-stars'
                : path === STUDIO_PATH
                  ? 'studio'
                  : null

  const onNavigate = useCallback(
    (destination: NavDestination) => {
      if (destination === 'home') navigate(HOME_PATH)
      else if (destination === 'designs') navigate(MY_DESIGNS_PATH)
      else if (destination === 'looks') navigate(MY_LOOKS_PATH)
      else if (destination === 'croquis') navigate(MY_CROQUIS_PATH)
      else if (destination === 'fashion-stars') navigate(FASHION_STARS_PATH)
      else navigate(STUDIO_PATH)
    },
    [navigate],
  )
  const backToStudio = useCallback(() => navigate(STUDIO_PATH), [navigate])
  const backToLooks = useCallback(() => navigate(MY_LOOKS_PATH), [navigate])
  const useCroquisInStudio = useCallback(
    (croquisId: string, version: number) => {
      editor.requestPersonalCroquisPin(croquisId, version)
      navigate(STUDIO_PATH)
    },
    [editor, navigate],
  )
  const focusLookId = searchParams.get('look')
  const clearFocusLook = useCallback(() => {
    if (!searchParams.has('look')) return
    const next = new URLSearchParams(searchParams)
    next.delete('look')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const currentNav: NavDestination = useMemo(() => {
    if (view === 'home') return 'home'
    if (view === 'library') return 'designs'
    if (view === 'looks' || view === 'techpack') return 'looks'
    if (view === 'croquis') return 'croquis'
    if (view === 'fashion-stars') return 'fashion-stars'
    return 'create'
  }, [view])

  if (view === null) return <Navigate to={HOME_PATH} replace />

  return (
    <div className={`${styles.page} studioShellRoot studio-chrome`}>
      <FashionRiseAppShell
        username={editor.user?.username ?? 'Creator'}
        onLogout={editor.onLogout}
        onComingSoon={editor.showComingSoon}
        currentNav={currentNav}
        onNavigate={onNavigate}
      >
        {view === 'home' ? (
          <HomeScreen
            username={editor.user?.username ?? 'Creator'}
            onNavigate={onNavigate}
          />
        ) : view === 'fashion-stars' ? (
          <FashionStarsScreen
            onOpenCreate={() => onNavigate('create')}
            onOpenLooks={() => onNavigate('looks')}
          />
        ) : view === 'library' && editor.user?.id ? (
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
              personalCroquisId: editor.personalCroquisId,
              personalCroquisVersion: editor.personalCroquisVersion,
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
            onOpenTechpack={(draftId) => navigate(`${TECHPACK_PATH_PREFIX}/${draftId}`)}
          />
        ) : view === 'croquis' ? (
          <MyCroquisScreen
            onBackToStudio={backToStudio}
            onUseInStudio={useCroquisInStudio}
            activeStudioPinId={editor.personalCroquisId}
            libraryVersion={editor.libraryVersion}
          />
        ) : view === 'techpack' && techpackDraftId ? (
          <TechpackScreen draftId={techpackDraftId} onBack={backToLooks} />
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
