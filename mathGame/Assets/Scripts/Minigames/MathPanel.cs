using System;
using System.Collections;
using System.Collections.Generic;
using MathGame.Player;
using UnityEngine;
using UnityEngine.UI;

namespace MathGame.Minigames
{
    public class MathPanel : MonoBehaviour
    {
        [SerializeField] PlayerController player;
        [SerializeField] GameObject root;
        [SerializeField] Text promptLabel;
        [SerializeField] Text feedbackLabel;
        [SerializeField] Button[] answerButtons;
        [SerializeField] Text[] answerLabels;
        [SerializeField] string wrongMessage = "Not quite. Try again.";
        [SerializeField, Min(0.2f)] float successDelay = 1.1f;

        MathChallenge _challenge;
        Action _onSuccess;
        bool _open;
        bool _holdsLock;
        bool _accepting;
        Coroutine _closeRoutine;
        string _successMessage = "Correct!";

        public bool IsOpen => _open;

        void Awake()
        {
            if (answerButtons == null)
                return;

            for (int i = 0; i < answerButtons.Length; i++)
            {
                int index = i;
                if (answerButtons[i] != null)
                    answerButtons[i].onClick.AddListener(() => Choose(index));
            }

            HideImmediate();
        }

        void OnDestroy()
        {
            if (answerButtons != null)
            {
                for (int i = 0; i < answerButtons.Length; i++)
                {
                    if (answerButtons[i] != null)
                        answerButtons[i].onClick.RemoveAllListeners();
                }
            }

            ReleaseLock();
        }

        public void Open(MathChallenge challenge, string successMessage, Action onSuccess)
        {
            if (challenge == null)
            {
                onSuccess?.Invoke();
                return;
            }

            if (_closeRoutine != null)
            {
                StopCoroutine(_closeRoutine);
                _closeRoutine = null;
            }

            _challenge = challenge;
            _onSuccess = onSuccess;
            _open = true;
            _accepting = true;
            HoldLock();

            if (root != null)
                root.SetActive(true);

            if (promptLabel != null)
                promptLabel.text = challenge.Prompt;

            if (feedbackLabel != null)
                feedbackLabel.text = string.Empty;

            IReadOnlyList<string> answers = challenge.Answers;
            int count = answerButtons != null ? answerButtons.Length : 0;
            for (int i = 0; i < count; i++)
            {
                bool hasAnswer = answers != null && i < answers.Count;
                if (answerButtons[i] != null)
                {
                    answerButtons[i].gameObject.SetActive(hasAnswer);
                    answerButtons[i].interactable = true;
                }

                if (answerLabels != null && i < answerLabels.Length && answerLabels[i] != null)
                    answerLabels[i].text = hasAnswer ? answers[i] : string.Empty;
            }

            _successMessage = string.IsNullOrEmpty(successMessage) ? "Correct!" : successMessage;
        }

        void Choose(int index)
        {
            if (!_open || !_accepting || _challenge == null)
                return;

            if (_challenge.IsCorrect(index))
            {
                _accepting = false;
                SetButtonsInteractable(false);
                if (feedbackLabel != null)
                    feedbackLabel.text = _successMessage;

                Action success = _onSuccess;
                _onSuccess = null;
                success?.Invoke();
                _closeRoutine = StartCoroutine(CloseAfterDelay());
                return;
            }

            if (feedbackLabel != null)
                feedbackLabel.text = wrongMessage;
        }

        IEnumerator CloseAfterDelay()
        {
            yield return new WaitForSecondsRealtime(successDelay);
            _closeRoutine = null;
            Close();
        }

        void Close()
        {
            _open = false;
            _accepting = false;
            _challenge = null;
            HideImmediate();
            ReleaseLock();
        }

        void HideImmediate()
        {
            if (root != null)
                root.SetActive(false);
        }

        void SetButtonsInteractable(bool value)
        {
            if (answerButtons == null)
                return;

            for (int i = 0; i < answerButtons.Length; i++)
            {
                if (answerButtons[i] != null)
                    answerButtons[i].interactable = value;
            }
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
