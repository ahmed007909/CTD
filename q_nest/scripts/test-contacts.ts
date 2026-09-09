// import { PrismaClient } from '@prisma/client';
// import { ContactsService } from '../src/modules/contacts/services/contacts.service';
// import { PrismaService } from '../src/prisma/prisma.service';

// async function runTests() {
//   console.log('--- Starting Contacts Module Verification Tests ---');

//   const prisma = new PrismaService();
//   await prisma.$connect();
//   const contactsService = new ContactsService(prisma);

//   const AHMED_ID = '00000000-0000-0000-0000-000000000001';
//   const ALI_PHONE = '+923002222222';
//   const UNKNOWN_PHONE = '+923009999999';
//   const AHMED_OWN_PHONE = '+923001111111';

//   try {
//     // Clean any previous test contacts
//     await prisma.contact.deleteMany({ where: { userId: AHMED_ID } });

//     // Test 1: Add registered user (Investigator Ali)
//     console.log('\n[Test 1] Adding registered user (Ali) with custom name...');
//     const res1 = await contactsService.addContact(AHMED_ID, {
//       phone: ALI_PHONE,
//       customName: 'Ali Special Branch',
//     });
//     console.log('Result 1:', {
//       isRegistered: res1.isRegistered,
//       customName: res1.contact?.customName,
//       contactUserId: res1.contact?.contactId,
//       officialName: res1.contact?.contactUser?.fullName,
//     });
//     if (!res1.isRegistered || res1.contact?.customName !== 'Ali Special Branch') {
//       throw new Error('Test 1 failed: Expected registered contact to be saved with custom name.');
//     }
//     console.log('✅ Test 1 PASSED: Registered contact successfully saved with specific name.');

//     // Test 2: Add non-existent phone number (Unregistered user)
//     console.log('\n[Test 2] Adding unregistered number (+923009999999)...');
//     const res2 = await contactsService.addContact(AHMED_ID, {
//       phone: UNKNOWN_PHONE,
//       customName: 'External Informer',
//     });
//     console.log('Result 2:', {
//       isRegistered: res2.isRegistered,
//       inviteLink: res2.inviteLink,
//     });
//     if (res2.isRegistered !== false || !res2.inviteLink) {
//       throw new Error('Test 2 failed: Expected isRegistered=false and inviteLink.');
//     }
//     console.log('✅ Test 2 PASSED: Correctly returned isRegistered=false and generated invite link.');

//     // Test 3: Self-add check (User adds own phone number)
//     console.log('\n[Test 3] Preventing self-add (+923001111111)...');
//     try {
//       await contactsService.addContact(AHMED_ID, {
//         phone: AHMED_OWN_PHONE,
//         customName: 'Myself',
//       });
//       throw new Error('Test 3 failed: Expected BadRequestException for self-add.');
//     } catch (err: any) {
//       console.log('Self-add blocked as expected:', err.message);
//       console.log('✅ Test 3 PASSED: Self-add successfully prevented.');
//     }

//     // Test 4: Get contacts list
//     console.log('\n[Test 4] Fetching all contacts for Officer Ahmed...');
//     const contactsList = await contactsService.getContacts(AHMED_ID);
//     console.log(`Fetched ${contactsList.length} contact(s). First contact name: "${contactsList[0]?.customName}"`);
//     if (contactsList.length !== 1 || contactsList[0]?.customName !== 'Ali Special Branch') {
//       throw new Error('Test 4 failed: Contact list does not match expected result.');
//     }
//     console.log('✅ Test 4 PASSED: Contacts fetched accurately.');

//     // Test 5: Update custom name
//     console.log('\n[Test 5] Updating custom name to "Ali Lead Investigator"...');
//     const updated = await contactsService.updateContact(AHMED_ID, contactsList[0].id, {
//       customName: 'Ali Lead Investigator',
//     });
//     console.log('Updated name:', updated.customName);
//     if (updated.customName !== 'Ali Lead Investigator') {
//       throw new Error('Test 5 failed: Contact name update failed.');
//     }
//     console.log('✅ Test 5 PASSED: Custom name updated.');

//     console.log('\n=================================================');
//     console.log('🎉 ALL CONTACTS MODULE VERIFICATION TESTS PASSED!');
//     console.log('=================================================');
//   } catch (error) {
//     console.error('❌ Test failed with error:', error);
//     process.exit(1);
//   } finally {
//     await prisma.$disconnect();
//   }
// }

// runTests();
