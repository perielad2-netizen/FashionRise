import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { isFittingRoomUiEnabled } from '@/config/fittingRoomUi'
import { isMyCroquisUiEnabled } from '@/config/myCroquisUi'
import { FashionRiseAppShell } from '@/shell/components/FashionRiseAppShell'
import { CreatorWorkspace } from '@/shell/components/CreatorWorkspace'
import { FittingRoomScreen } from '@/shell/components/FittingRoomScreen'
import { HomeScreen } from '@/shell/components/HomeScreen'
import { RunwayBoardScreen } from '@/shell/components/RunwayBoardScreen'
import { RunwayScreen } from '@/shell/components/RunwayScreen'
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
export const FITTING_ROOM_PATH = '/studio/fitting-room'
/** FashionRise = Instagram-style immersive social feed. */
export const FASHIONRISE_PATH = '/studio/fashionrise'
/** Runway = rankings + weekly competition results (not the immersive feed). */
export const RUNWAY_PATH = '/studio/runway'
/** Opens FashionRise directly into My Profile (edit). */
export const RUNWAY_MY_PROFILE_PATH = `${FASHIONRISE_PATH}?profile=me`
/** Opens FashionRise Manage friends. */
export const RUNWAY_FRIENDS_PATH = `${FASHIONRISE_PATH}?friends=1`
/** @deprecated legacy Fashion Stars path — redirects to FashionRise feed */
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
  const fittingRoomEnabled = isFittingRoomUiEnabled()
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
            : path === FITTING_ROOM_PATH
              ? fittingRoomEnabled
                ? 'fitting-room'
                : null
              : path === HOME_PATH
                ? 'home'
                : path === FASHIONRISE_PATH || path === FASHION_STARS_PATH
                  ? 'fashionrise'
                  : path === RUNWAY_PATH
                    ? 'runway'
                    : path === STUDIO_PATH
                      ? 'studio'
                      : null

  const onNavigate = useCallback(
    (destination: NavDestination) => {
      if (destination === 'home') navigate(HOME_PATH)
      else if (destination === 'designs') navigate(MY_DESIGNS_PATH)
      else if (destination === 'looks') navigate(MY_LOOKS_PATH)
      else if (destination === 'croquis') navigate(MY_CROQUIS_PATH)
      else if (destination === 'fitting-room') navigate(FITTING_ROOM_PATH)
      else if (destination === 'fashionrise') navigate(FASHIONRISE_PATH)
      else if (destination === 'runway') navigate(RUNWAY_PATH)
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
  const openOwnProfile = searchParams.get('profile') === 'me'
  const openFriends = searchParams.get('friends') === '1'
  /** false while designer profile / Friends manage (or left FashionRise feed) — keeps GlobalHeader visible. */
  const [fashionRiseImmersiveFeed, setFashionRiseImmersiveFeed] = useState(true)
  const [fashionRiseFeedFocusToken, setFashionRiseFeedFocusToken] = useState(0)
  useEffect(() => {
    if (view !== 'fashionrise') setFashionRiseImmersiveFeed(true)
  }, [view])
  const clearFocusLook = useCallback(() => {
    if (!searchParams.has('look')) return
    const next = new URLSearchParams(searchParams)
    next.delete('look')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])
  const clearOwnProfileParam = useCallback(() => {
    if (!searchParams.has('profile')) return
    const next = new URLSearchParams(searchParams)
    next.delete('profile')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])
  const clearFriendsParam = useCallback(() => {
    if (!searchParams.has('friends')) return
    const next = new URLSearchParams(searchParams)
    next.delete('friends')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])
  const openMyProfile = useCallback(() => {
    navigate(RUNWAY_MY_PROFILE_PATH)
  }, [navigate])
  const openFriendsPage = useCallback(() => {
    navigate(RUNWAY_FRIENDS_PATH)
  }, [navigate])
  const focusFashionRiseFeed = useCallback(() => {
    setFashionRiseImmersiveFeed(true)
    setFashionRiseFeedFocusToken((n) => n + 1)
    navigate(FASHIONRISE_PATH)
  }, [navigate])

  const currentNav: NavDestination = useMemo(() => {
    if (view === 'home') return 'home'
    if (view === 'library') return 'designs'
    if (view === 'looks' || view === 'techpack') return 'looks'
    if (view === 'croquis') return 'croquis'
    if (view === 'fitting-room') return 'fitting-room'
    if (view === 'fashionrise') return 'fashionrise'
    if (view === 'runway') return 'runway'
    return 'create'
  }, [view])

  const onShellNavigate = useCallback(
    (destination: NavDestination) => {
      if (destination === 'fashionrise') {
        focusFashionRiseFeed()
        return
      }
      onNavigate(destination)
    },
    [focusFashionRiseFeed, onNavigate],
  )

  if (view === null) return <Navigate to={HOME_PATH} replace />
  if (path === FASHION_STARS_PATH) return <Navigate to={FASHIONRISE_PATH} replace />

  // Full-bleed immersive chrome is FashionRise feed only. Runway rankings,
  // profile, Friends, and every other studio page keep GlobalHeader + nav.
  const immersive = view === 'fashionrise' && fashionRiseImmersiveFeed

  return (
    <div className={`${styles.page} studioShellRoot studio-chrome`}>
      <FashionRiseAppShell
        username={editor.user?.username ?? 'Creator'}
        onLogout={editor.onLogout}
        onComingSoon={editor.showComingSoon}
        currentNav={currentNav}
        onNavigate={onShellNavigate}
        onOpenProfile={openMyProfile}
        onOpenFriends={openFriendsPage}
        immersive={immersive}
      >
        {view === 'home' ? (
          <HomeScreen
            username={editor.user?.username ?? 'Creator'}
            onNavigate={onShellNavigate}
          />
        ) : view === 'fashionrise' ? (
          <RunwayScreen
            onOpenCreate={() => onShellNavigate('create')}
            onOpenLooks={() => onShellNavigate('looks')}
            onOpenFittingRoom={
              fittingRoomEnabled ? () => onShellNavigate('fitting-room') : undefined
            }
            openOwnProfile={openOwnProfile}
            onOwnProfileConsumed={clearOwnProfileParam}
            openFriends={openFriends}
            onFriendsConsumed={clearFriendsParam}
            onImmersiveFeedChange={setFashionRiseImmersiveFeed}
            feedFocusToken={fashionRiseFeedFocusToken}
          />
        ) : view === 'runway' ? (
          <RunwayBoardScreen />
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
        ) : view === 'fitting-room' && editor.user?.id ? (
          <FittingRoomScreen userId={editor.user.id} onBackToStudio={backToStudio} />
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
            editor.continueOpenAfterConflictInStudio()
            backToStudio()
          }}
        />
      ) : null}
    </div>
  )
}
