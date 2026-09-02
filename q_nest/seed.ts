import { PrismaClient, Role, GroupMemberRole } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

// Fixed UUIDs — jo test client / frontend me hardcode karne hain
const USER1_ID = '00000000-0000-0000-0000-000000000001'; // Officer Ahmed
const USER2_ID = '00000000-0000-0000-0000-000000000002'; // Investigator Ali
const GROUP_ID = '00000000-0000-0000-0000-000000000010'; // CTD QRU (group chat)
const DEPARTMENT_ID = '00000000-0000-0000-0000-0000000000d1';

async function main() {
  console.log('Seeding started...');

  // 1. Department
  await prisma.department.upsert({
    where: { id: DEPARTMENT_ID },
    update: {},
    create: {
      id: DEPARTMENT_ID,
      name: 'CTD Sindh',
    },
  });

  const passwordHash = await bcrypt.hash('Test@1234', 10);

  // 2. User 1 - Officer Ahmed
  const user1 = await prisma.user.upsert({
    where: { id: USER1_ID },
    update: {},
    create: {
      id: USER1_ID,
      username: 'officer_ahmed',
      cnic: '4210112345671',
      phone: '03001234567',
      passwordHash,
      fullName: 'Ahmed Abbasi',
      role: Role.officer,
      departmentId: DEPARTMENT_ID,
      designation: 'Field Officer',
    },
  });

  // 3. User 2 - Investigator Ali
  const user2 = await prisma.user.upsert({
    where: { id: USER2_ID },
    update: {},
    create: {
      id: USER2_ID,
      username: 'investigator_ali',
      cnic: '4210112345672',
      phone: '03007654321',
      passwordHash,
      fullName: 'Ali Raza',
      role: Role.investigator,
      departmentId: DEPARTMENT_ID,
      designation: 'Investigation Unit',
    },
  });

  // 4. Group - CTD QRU
  const group = await prisma.group.upsert({
    where: { id: GROUP_ID },
    update: {},
    create: {
      id: GROUP_ID,
      groupName: 'CTD QRU',
      createdBy: user1.id,
    },
  });

  // 5. Group members (dono users ko group me daal do)
  await prisma.groupMember.upsert({
    where: { groupId_userId: { groupId: group.id, userId: user1.id } },
    update: {},
    create: {
      groupId: group.id,
      userId: user1.id,
      roleInGroup: GroupMemberRole.admin,
    },
  });

  await prisma.groupMember.upsert({
    where: { groupId_userId: { groupId: group.id, userId: user2.id } },
    update: {},
    create: {
      groupId: group.id,
      userId: user2.id,
      roleInGroup: GroupMemberRole.member,
    },
  });

  console.log('Seeding done ✅');
  console.log('User 1 (Officer Ahmed):', user1.id);
  console.log('User 2 (Investigator Ali):', user2.id);
  console.log('Group (CTD QRU):', group.id);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });