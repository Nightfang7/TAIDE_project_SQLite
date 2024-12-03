let mediaRecorder;
let audioChunks = [];
let currentEditId = null;
let recordModal;

async function updateRecord() {
    const datePicker = document.querySelector('.date-picker');
    const updatedData = {
        Food: document.querySelector('.modal-food').value,
        'Food Quantity': document.querySelector('.modal-food-quantity').value,
        Exercise: document.querySelector('.modal-exercise').value,
        'Exercise Quantity': document.querySelector('.modal-exercise-quantity').value,
        'Other Key Info': document.querySelector('.modal-other-info').value
    };

    try {
        const response = await fetch(`/update_record/${currentEditId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedData)
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Response:', data); // Log response
            showNotification('更新成功');
            recordModal.hide();
            loadRecords(datePicker.value);
        } else {
            const error = await response.json();
            console.error('Error:', error);
            showNotification('更新失敗');
        }
    } catch (error) {
        showNotification('更新失敗');
        console.error('Update failed:', error);
    }
}

function showNotification(message) {
    const notification = document.getElementById('notification');
    const toastBody = notification.querySelector('.toast-body');
    toastBody.textContent = message;
    
    const toast = new bootstrap.Toast(notification, {
        delay: 2000
    });
    toast.show();
}

async function loadRecords(date) {
    try {
        const response = await fetch(`/get_records_by_date/${date}`);
        if (response.ok) {
            const records = await response.json();
            displayRecords(records);
        } else {
            throw new Error('無法載入記錄');
        }
    } catch (error) {
        console.error(error);
    }
}

function displayRecords(records) {
    const tbody = document.getElementById('records-body');
    tbody.innerHTML = '';
    
    if (!records || records.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="6" style="text-align: center;">目前尚無記錄</td>
        `;
        tbody.appendChild(row);
        return;
    }

    records.forEach(record => {
        const row = document.createElement('tr');
        row.onclick = () => openEditModal(record);
        row.innerHTML = `
            <td>${record.food || '-'}</td>
            <td>${record.food_quantity || '-'}</td>
            <td>${record.exercise || '-'}</td>
            <td>${record.exercise_quantity || '-'}</td>
            <td>${record.other_info || '-'}</td>
            <td>${record.record_time}</td>
        `;
        tbody.appendChild(row);
    });
}

function openEditModal(record) {
    if (!recordModal) {
        recordModal = new bootstrap.Modal(document.getElementById('recordModal'));
    }
    currentEditId = record.id;
    document.querySelector('.modal-food').value = record.food;
    document.querySelector('.modal-food-quantity').value = record.food_quantity;
    document.querySelector('.modal-exercise').value = record.exercise;
    document.querySelector('.modal-exercise-quantity').value = record.exercise_quantity;
    document.querySelector('.modal-other-info').value = record.other_info;
    recordModal.show();
}

let deleteConfirmModal;

function confirmDelete() {
    deleteConfirmModal.show();
}

async function deleteRecord() {
    const datePicker = document.querySelector('.date-picker');
    try {
        const response = await fetch(`/delete_record/${currentEditId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification('記錄已刪除');
            deleteConfirmModal.hide();
            recordModal.hide();
            loadRecords(datePicker.value);
        } else {
            throw new Error('刪除失敗');
        }
    } catch (error) {
        showNotification('刪除失敗');
        console.error('Delete failed:', error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
   const micButton = document.querySelector('.mic-button');
   const voiceInput = document.querySelector('.voice-input');
   const taideButton = document.querySelector('.taide-button');
   const statusMessage = document.querySelector('.status-message'); 
   const resultInputs = document.querySelectorAll('.result-input');
   const resultTextarea = document.querySelector('.result-textarea');
   const confirmButton = document.querySelector('.confirm-button');
   const cancelButton = document.querySelector('.cancel-button');
   const searchButton = document.querySelector('.search-button');
   const datePicker = document.querySelector('.date-picker');
   const dateInput = document.querySelector('.date-input');
   dateInput.valueAsDate = new Date();  // Set to today

   recordModal = new bootstrap.Modal(document.getElementById('recordModal'));
   datePicker.valueAsDate = new Date();

   deleteConfirmModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));

   async function startRecording() {
       document.getElementById('recording-spinner').classList.remove('d-none');
       micButton.querySelector('.bi-mic').style.color = '#ff4444';
       clearResults();
       try {
           const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
           mediaRecorder = new MediaRecorder(stream);
           audioChunks = [];

           mediaRecorder.ondataavailable = (event) => {
               audioChunks.push(event.data);
           };

           mediaRecorder.onstop = async () => {
               const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
               await processAudio(audioBlob);
           };

           mediaRecorder.start();
           statusMessage.textContent = '錄音中...';
       } catch (error) {
           document.getElementById('recording-spinner').classList.add('d-none');
           statusMessage.textContent = '無法使用麥克風';
           micButton.querySelector('.bi-mic').style.color = '#00ADB5';
           console.error(error);
       }
   }

   function stopRecording() {
       micButton.querySelector('.bi-mic').style.color = '#00ADB5';
       document.getElementById('recording-spinner').classList.add('d-none');
       if (mediaRecorder && mediaRecorder.state === 'recording') {
           mediaRecorder.stop();
           mediaRecorder.stream.getTracks().forEach(track => {
                track.stop();
            });
           statusMessage.textContent = '處理語音中...';
       }
   }

   async function processAudio(audioBlob) {
       const formData = new FormData();
       formData.append('audio', audioBlob);

       try {
           const response = await fetch('/recognize', {
               method: 'POST',
               body: formData
           });

           if (response.ok) {
               const data = await response.json();
               console.log('Voice recognition result:', data.text); // Debug log
               voiceInput.value = data.text;
               statusMessage.textContent = '語音辨識完成';
           } else {
               throw new Error('語音辨識失敗');
           }
       } catch (error) {
           console.error('Recognition error:', error);
           statusMessage.textContent = error.message;
       }
   }

   async function processTaide() {
       const text = voiceInput.value.trim();
       console.log('Input text:', text); // Debug logging

       if (!text) {
           statusMessage.textContent = '請輸入文字';
           return;
       }

       statusMessage.textContent = 'TAIDE處理中...';
       document.getElementById('loading-spinner').classList.remove('d-none');

       try {
           console.log('Sending text:', { text }); // Debug log
           const response = await fetch('/process_taide', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: voiceInput.value })
           });

           console.log('Request data:', { text: voiceInput.value }); // Add logging

           if (response.ok) {
                const data = await response.json();
                console.log('Success response data:', data); // Add logging
                // clearResults();
                displayResults(data.output);
           } else {
                const errorData = await response.json();
                console.log('Error data:', errorData); // Add logging
                throw new Error('TAIDE處理失敗');
           }
       } catch (error) {
            console.error('TAIDE error:', error); // Add logging
            statusMessage.textContent = error.message;
       } finally {
            document.getElementById('loading-spinner').classList.add('d-none');
       }
   }

   function displayResults(results) {
       resultInputs[0].value = results.Food;
       resultInputs[1].value = results['Food Quantity'];
       resultInputs[2].value = results.Exercise;
       resultInputs[3].value = results['Exercise Quantity'];
       resultTextarea.value = results['Other Key Info'];

       enableEditing(true);
       statusMessage.textContent = '分析成功, 請按"確認"保存記錄';
   }

   function enableEditing(enable) {
       resultInputs.forEach(input => {
           input.disabled = !enable;
       });
       resultTextarea.disabled = !enable;
       confirmButton.style.display = enable ? 'inline' : 'none';
       cancelButton.style.display = enable ? 'inline' : 'none';
   }

   async function saveRecord() {
       const record = {
           Food: resultInputs[0].value,
           'Food Quantity': resultInputs[1].value,
           Exercise: resultInputs[2].value,
           'Exercise Quantity': resultInputs[3].value,
           'Other Key Info': resultTextarea.value,
           'record_date': document.querySelector('.date-input').value
       };

       try {
           const response = await fetch('/save_record', {
               method: 'POST',
               headers: { 'Content-Type': 'application/json' },
               body: JSON.stringify(record)
           });

           if (response.ok) {
               showNotification('記錄已保存'); 
               enableEditing(false);
               clearConfirmationMessage();
               loadRecords(datePicker.value);
           } else {
               throw new Error('保存失敗');
           }
       } catch (error) {
            showNotification('保存失敗');
       }
   }

   function clearResults() {
       resultInputs.forEach(input => input.value = '');
       resultTextarea.value = '';
       enableEditing(false);
       statusMessage.textContent = '';
       voiceInput.value = '';
   }

   function clearConfirmationMessage() {
       statusMessage.textContent = '';
       voiceInput.value = '';
       resultInputs.forEach(input => input.value = '');
       resultTextarea.value = '';
   }

   // Event listeners
   micButton.addEventListener('click', () => {
       if (!mediaRecorder || mediaRecorder.state === 'inactive') {
           startRecording();
       } else {
           stopRecording();
       }
   });

   taideButton.addEventListener('click', processTaide);
   confirmButton.addEventListener('click', saveRecord);
   cancelButton.addEventListener('click', clearResults);
   searchButton.addEventListener('click', () => loadRecords(datePicker.value));
//    datePicker.addEventListener('change', (e) => loadRecords(e.target.value));

   // Load initial records
   loadRecords(datePicker.value);
});