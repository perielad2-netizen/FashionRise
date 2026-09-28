using System;
using MathGame.Player;
using UnityEngine;
using UnityEngine.UI;

namespace MathGame.Dialogue
{
    public class DialogueUI : MonoBehaviour
    {
        [SerializeField] PlayerController player;
        [SerializeField] GameObject root;
        [SerializeField] Text speakerLabel;
        [SerializeField] Text lineLabel;
        [SerializeField] Button continueButton;
        [SerializeField] Text continueLabel;

        DialogueAsset _asset;
        int _index;
        int _openedFrame;
        bool _open;
        bool _holdsLock;
        Action _onClosed;

        public bool IsOpen => _open;

        void Awake()
        {
            if (continueButton != null)
                continueButton.onClick.AddListener(Advance);

            HideImmediate();
        }

        void OnDestroy()
        {
            if (continueButton != null)
                continueButton.onClick.RemoveListener(Advance);

            ReleaseLock();
        }

        void Update()
        {
            if (!_open || Time.frameCount == _openedFrame)
                return;

            if (Input.GetKeyDown(KeyCode.E) || Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.Space))
                Advance();
        }

        public void Show(DialogueAsset asset, Action onClosed)
        {
            _asset = asset;
            _onClosed = onClosed;
            _index = 0;
            _open = true;
            _openedFrame = Time.frameCount;
            HoldLock();

            if (root != null)
                root.SetActive(true);

            Refresh();
        }

        public void Advance()
        {
            if (!_open || _asset == null)
                return;

            if (_index < _asset.LineCount - 1)
            {
                _index++;
                Refresh();
                return;
            }

            Close();
        }

        void Refresh()
        {
            if (speakerLabel != null)
                speakerLabel.text = _asset != null ? _asset.SpeakerName : string.Empty;

            if (lineLabel != null)
                lineLabel.text = _asset != null ? _asset.GetLine(_index) : string.Empty;

            bool last = _asset == null || _index >= _asset.LineCount - 1;
            if (continueLabel != null)
                continueLabel.text = last ? "Close" : "Continue";
        }

        void Close()
        {
            Action callback = _onClosed;
            _onClosed = null;
            _asset = null;
            _open = false;
            HideImmediate();
            callback?.Invoke();
            if (!_open)
                ReleaseLock();
        }

        void HideImmediate()
        {
            if (root != null)
                root.SetActive(false);
        }

        void HoldLock()
        {
            if (_holdsLock || player == null)
                return;

            player.PushMovementLock();
            _holdsLock = true;
        }

        void ReleaseLock()
        {
            if (!_holdsLock || player == null)
                return;

            player.PopMovementLock();
            _holdsLock = false;
        }
    }
}
