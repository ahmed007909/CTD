import { PrismaClient, Role, GroupMemberRole } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('[Seed] Seeding CTD test database records...');

  // 1. Department
  const dept = await prisma.department.upsert({
    where: { id: '00000000-0000-0000-0000-000000000100' },
    update: { name: 'Counter Terrorism Department (CTD)' },
    create: {
      id: '00000000-0000-0000-0000-000000000100',
      name: 'Counter Terrorism Department (CTD)',
    },
  });
  console.log(`[Seed] Department: ${dept.name} (${dept.id})`);

  // 2. User 1: Officer Ahmed
  const user1 = await prisma.user.upsert({
    where: { id: '00000000-0000-0000-0000-000000000001' },
    update: {
      username: 'officer_ahmed',
      fullName: 'Officer Ahmed',
    },
    create: {
      id: '00000000-0000-0000-0000-000000000001',
      username: 'officer_ahmed',
      cnic: '11111-1111111-1',
      phone: '+923001111111',
      passwordHash: 'dummy_seeded_password_hash',
      fullName: 'Officer Ahmed',
      role: Role.officer,
      departmentId: dept.id,
      designation: 'Sub Inspector',
    },
  });
  console.log(`[Seed] User 1: ${user1.fullName} (${user1.id})`);

  // 3. User 2: Investigator Ali
  const user2 = await prisma.user.upsert({
    where: { id: '00000000-0000-0000-0000-000000000002' },
    update: {
      username: 'investigator_ali',
      fullName: 'Investigator Ali',
    },
    create: {
      id: '00000000-0000-0000-0000-000000000002',
      username: 'investigator_ali',
      cnic: '22222-2222222-2',
      phone: '+923002222222',
      passwordHash: 'dummy_seeded_password_hash',
      fullName: 'Investigator Ali',
      role: Role.investigator,
      departmentId: dept.id,
      designation: 'Lead Investigator',
    },
  });
  console.log(`[Seed] User 2: ${user2.fullName} (${user2.id})`);

  // 4. Test Group
  const group = await prisma.group.upsert({
    where: { id: '00000000-0000-0000-0000-000000000010' },
    update: { groupName: 'CTD Quick Response Unit' },
    create: {
      id: '00000000-0000-0000-0000-000000000010',
      groupName: 'CTD Quick Response Unit',
      createdBy: user1.id,
    },
  });
  console.log(`[Seed] Group: ${group.groupName} (${group.id})`);

  // 5. Add memberships
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
  console.log('[Seed] Added User 1 and User 2 to Group.');

  console.log('\n========================================');
  console.log('✅ DATABASE SEED COMPLETED SUCCESSFULLY!');
  console.log('========================================');
  console.log('Copy these IDs for testing in index.html:');
  console.log(`User 1 ID:  ${user1.id} (Officer Ahmed)`);
  console.log(`User 2 ID:  ${user2.id} (Investigator Ali)`);
  console.log(`Group ID:   ${group.id} (CTD Quick Response Unit)`);
  console.log('========================================\n');
}

main()
  .catch((e) => {
    console.error('[Seed Error]:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
