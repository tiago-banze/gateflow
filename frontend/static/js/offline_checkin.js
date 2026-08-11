/**
 * offline_checkin.js
 * Camada de dados offline do check-in, em IndexedDB. Dois object stores:
 *   - "guests": cópia local da lista de convidados do evento (chave: id),
 *     atualizada sempre que checkin.js busca a lista com sucesso online.
 *   - "pending": fila de check-ins feitos OFFLINE, ainda não confirmados
 *     pelo servidor (chave: auto-incremento).
 *
 * Uso (ver checkin.js):
 *   await OfflineCheckin.ready(eventId)
 *   await OfflineCheckin.cacheGuests(guests)
 *   OfflineCheckin.findGuest(guestId | qrValue)
 *   await OfflineCheckin.queueCheckin(guestId, checkedInBy)
 *   await OfflineCheckin.syncPending(apiRequestFn)
 */

const OfflineCheckin = (() => {
  const DB_NAME = "gateflow-checkin";
  const DB_VERSION = 1;
  let dbPromise = null;
  let currentEventId = null;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB não é suportado neste navegador."));
        return;
      }
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("guests")) {
          const store = db.createObjectStore("guests", { keyPath: "id" });
          store.createIndex("event_id", "event_id", { unique: false });
        }
        if (!db.objectStoreNames.contains("pending")) {
          db.createObjectStore("pending", { keyPath: "local_id", autoIncrement: true });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  async function ready(eventId) {
    currentEventId = eventId;
    try {
      await openDb();
      return true;
    } catch (e) {
      console.warn("Offline check-in indisponível:", e);
      return false;
    }
  }

  /** Substitui a cópia local dos convidados deste evento pela lista mais recente do servidor. */
  async function cacheGuests(guests) {
    try {
      const db = await openDb();
      const tx = db.transaction("guests", "readwrite");
      const store = tx.objectStore("guests");
      const index = store.index("event_id");
      // Limpa só os convidados DESTE evento -- não mexe em caches de outros
      // eventos que o mesmo tablet possa ter guardado.
      const range = IDBKeyRange.only(currentEventId);
      const cursorReq = index.openCursor(range);
      await new Promise((resolve, reject) => {
        cursorReq.onsuccess = () => {
          const cursor = cursorReq.result;
          if (cursor) { cursor.delete(); cursor.continue(); } else { resolve(); }
        };
        cursorReq.onerror = () => reject(cursorReq.error);
      });
      guests.forEach((g) => store.put({ ...g, event_id: currentEventId }));
      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      });
    } catch (e) {
      console.warn("Falha ao guardar convidados offline:", e);
    }
  }

  /** Aplica localmente o resultado de um check-in (online ou offline) na cópia guardada. */
  async function markGuestCheckedIn(guestId) {
    try {
      const db = await openDb();
      const tx = db.transaction("guests", "readwrite");
      const store = tx.objectStore("guests");
      const guest = await new Promise((resolve, reject) => {
        const req = store.get(guestId);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
      if (guest) {
        guest.checked_in = 1;
        store.put(guest);
      }
    } catch (e) {
      console.warn("Falha ao atualizar convidado offline:", e);
    }
  }

  async function getAllGuests() {
    try {
      const db = await openDb();
      const tx = db.transaction("guests", "readonly");
      const index = tx.objectStore("guests").index("event_id");
      return await new Promise((resolve, reject) => {
        const req = index.getAll(IDBKeyRange.only(currentEventId));
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      return [];
    }
  }

  async function findGuestById(guestId) {
    try {
      const db = await openDb();
      const tx = db.transaction("guests", "readonly");
      return await new Promise((resolve, reject) => {
        const req = tx.objectStore("guests").get(guestId);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      return null;
    }
  }

  /**
   * Adiciona um check-in feito offline à fila de sincronização. Não
   * verifica duplicados aqui -- quem chama (checkin.js) já confirmou
   * localmente que o convidado ainda não estava marcado como presente.
   */
  async function queueCheckin(guestId, checkedInBy) {
    const db = await openDb();
    const tx = db.transaction("pending", "readwrite");
    tx.objectStore("pending").add({
      guest_id: guestId,
      event_id: currentEventId,
      checked_in_by: checkedInBy || null,
      queued_at: new Date().toISOString(),
    });
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    await markGuestCheckedIn(guestId);
  }

  async function countPending() {
    try {
      const db = await openDb();
      const tx = db.transaction("pending", "readonly");
      return await new Promise((resolve, reject) => {
        const req = tx.objectStore("pending").count();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    } catch (e) {
      return 0;
    }
  }

  /**
   * Envia a fila pendente para o servidor, um de cada vez (o endpoint
   * /api/checkin/manual/<id> já é seguro para repetir -- se o convidado
   * já tiver sido marcado por outra via nesse meio tempo, apenas
   * confirma sem duplicar). `apiRequestFn` é a função apiRequest() já
   * usada pelo resto do site (injetada para não duplicar código aqui).
   * Retorna {synced, failed}.
   */
  async function syncPending(apiRequestFn) {
    const db = await openDb();
    const all = await new Promise((resolve, reject) => {
      const tx = db.transaction("pending", "readonly");
      const req = tx.objectStore("pending").getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });

    let synced = 0;
    let failed = 0;

    for (const item of all) {
      try {
        const result = await apiRequestFn(`/api/checkin/manual/${item.guest_id}`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        // Sucesso OU "já confirmado antes" contam como sincronizado --
        // nos dois casos o servidor já reflete a presença do convidado.
        if (result.success || result.already_checked_in) {
          await new Promise((resolve, reject) => {
            const tx = db.transaction("pending", "readwrite");
            tx.objectStore("pending").delete(item.local_id);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
          });
          synced += 1;
        } else {
          failed += 1;
        }
      } catch (e) {
        failed += 1;
        // Ainda sem rede de verdade (falso positivo do evento 'online')
        // -- para a sincronização aqui, tenta de novo no próximo ciclo.
        break;
      }
    }

    return { synced, failed };
  }

  return {
    ready,
    cacheGuests,
    getAllGuests,
    findGuestById,
    markGuestCheckedIn,
    queueCheckin,
    countPending,
    syncPending,
  };
})();
