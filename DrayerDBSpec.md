
# The DrayerDB protocol

DrayerDB is a WIP embeddable database built on SQLite with 2 way sync via WebSockets.

Sync messages are connectionless, idempotent, and have their own encryption to safely send over any channel.

Sync is done via two keys, the send key and recieve key, using asymmetric crypto.

To recieve records, you only need the recieve key, but other nodes will not accept records from you unless you have the send key.

However, things like caching proxies are still possible in a limited fashion by storing and retransmitting the unmodified messages, if
you only care about recent data and don't need to request anything, or you have the spare bandwidth to send full copies of the whole DB.
This is theoretically possible but not implememted.


The basic data structure is a doubly-ordered pseudochain.  Conflict resolution is done by record timestamps, but individual nodes
also track arrival times. This means you can always ask a node if it has gotten any new records since you last contacted it.

The downside is that syncing with a new node the first time requires downloading their full list of records, as there is no global order.
This is probably fine for thousands to low millions of records, and tens of nodes.

You can also theoretically get around this if you are only interested in recent nodes.


## Record Structure

Every record is a JSON obj.  Custom application defined keys and types should use com.domain.foo formats to stay unambiguous.

Every record has an implicit full path.  This is the full chain of parent to child records, separated by /.

Common special keys:

### id(indexed)

The record UUID in canonical format.  Unique. New record with same ID replaces older.

###  time(indexed)

Integer timstamp, us since unix epoch. Used for conflict resolution.

### type(indexed)

String.  Custom types must be com.domain.x style.  Deletion is normally done by setting a record to the null type.
However in some cases you can silently delete a record without even telling other nodes.

Null records cannot be resurrected. You have to make a new record.

### name(indexed)
Records can have names that are useful for various app-specific purposes.

### parent(optional, indexed)
Every record can have a parent record.  When a parent record is set to type=null, all child records should be considered gone,
and can be silently deleted.  Keep this in mind as it allows you to avoid having huge amounts of nulls.

The parent does not have to exist yet.

The parent of field must be a full path. If you are C, your parent is B, and B's parent is A, your 'parent' field must be 'A/B', while your ID is C.


Note that IDs are still globally unique.  There cannot be another A in the database even with a different parent.

### autoclean(optional)
When this is set to something, it means that nodes can silently delete old records older than a locally configured date.  Use this for things like log entries.

When it is a nonempty string, it means nodes can delete old records silently, but must retain the very latest record in that "autoclean channel" no matter how old.

An "autoclean channel" is defined as the combination of (parent, autoclean).

This property can never be added to an existing record.  Nodes must silently ignore an incoming sync record that would do so. It cannot be changed on an existing record either.


## Wire protocol

There are 3 layers

### The outer layer as sent on the wire:

1 byte message type(must be a 1)

128bit KeyHint(first 16b of the double hash of pubkey)+

64 bit timestamp in us since UNIX epoch+

crypto_secetbox encoded protectedData, with the nonce being teh timestamp padded to 24bytes,
and the key being the single blake2b hash of the public key


### The protectedData:

32 byte sender public key
crypto_sign-ed inner message from that sender


### The inner message
8-byte timestamp
Payload

## Payload protocol
The payload is a JSON object that can have the following keys.

If we and a peer ar using the same physical DB, we may never get "get records" to send, because they would have put it in the shared DB before sending.

Implementions must detect this, and always trigger flushes for all all records arriving from our own nodeID to other nodes, as we explicitly
support multiple nodes sharing one sqlite database while using the protocol for IPC.

A flush is when you send every peer note all the records newer than hte last one you have sent them.

The "clock" starts from their first request, we don't send any records older than that, EXCEPT that we must always send all new records(And all records we just got told
about by peers sharing our same DB file!, because those peers likely don't share the same set of other peers as us!).

The reason for this is that when sharing a DB file the usual mechanism of requesting records newer than the last message breaks down. We do not want to
keep track of records sent to ourself every time, this would waste disk activity!!


So, any time we commit a set of records, or hear about a set, we trigger a flush which sends all peers every record in the DB which is newer than the oldest record in the incoming set.

Records have to be sent in contiguous blocks or else recordsStartFrom makes no sense!!

The exception is that we do not have to send a peer any records that originally arrived from that exact peer, for very obvious reasons.



### records

This is a list of records, where each record is a 3 element list:

* Record Data as string(JSON encoded)
* Record Signature made by: concat(24 byte Blake2b digest of record data, 8 byte blake2b of the sender's pubkey, crypto_sign_detached of the digest)
* Integer record arrival time, the time at which that record arrrived at the remote


### recordsStartFrom

An arrival time.  This indicates that there are no records in between the earliest record present in the records list, and this timestamp.
It is so the recierver can be sure they have all records to a point,




## Core Record Types

### post

Has title and body attributes, it represents a notification, note, social post, or other such text record.  If it has a parent, it is a comment.
{{ and }} are currently reserved

### row

Represents a generic data record to be used vaugely like an Excel data row.

Must be child of post.  It's database ID should be the parent's ID, a dash, then a lowercase spaceless name.  The 'name' can be the full
name with spaces.   The 'name' attribute should be directly user visible.

There should only be one item in a list with a name, attempting to create a duplicate shiould just take you to the existing.

Rows have data fields beginning with row. which can only be strings or numbers.  If a string looks like a number it should be treated as such.

